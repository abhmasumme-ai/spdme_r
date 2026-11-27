"""
Melbet Payload Capture — Standalone Tool
=========================================

চালানোর সময় URL জিজ্ঞেস করবে। আপনি টাইপ করবেন।
ফাঁকা রাখলে default Melbet homepage।

চালানো:
    python capture.py

বন্ধ: Ctrl+C (অথবা ব্রাউজার ক্লোজ করুন)
"""
import asyncio
import json
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from patchright.async_api import async_playwright

BASE = Path(__file__).resolve().parent
OUT_DIR = BASE / "melbet_payloads"
OUT_DIR.mkdir(exist_ok=True)
BETS_DIR = OUT_DIR / "bets"
BETS_DIR.mkdir(exist_ok=True)
PROFILE = BASE / "profile"

DEFAULT_URL = "https://melbet-7626.pro"

WICKET_KEYWORDS = ("wicket", "fall", " out", "dismiss", "fow")
BET_URL_HINTS = ("makebet", "betweb", "placebet", "/bet/", "oneclickbet")
HISTORY_URL_HINTS = ("bethistory", "getbets", "mybets", "historybet", "showbets")
REDACT_HEADERS = {"cookie", "authorization", "x-auth-token", "x-csrf-token",
                  "x-xsrf-token", "x-api-key", "set-cookie"}
MIN_SAVE_INTERVAL = 2.0

_last_save: dict[str, float] = {}
_prev_wicket_sig: dict[str, tuple] = {}
_seen_gids: set[str] = set()
_bet_count = 0


# ============================================================
#  URL — ম্যানুয়াল prompt (একমাত্র পথ)
# ============================================================
def ask_url() -> str:
    """সবসময় URL জিজ্ঞেস করে। ফাঁকা হলে default।"""
    print()
    print("─" * 68)
    print("  Melbet URL দিন")
    print("─" * 68)
    print("  উদাহরণ:")
    print("    https://melbet-7626.pro")
    print("    https://melbet-7626.pro/en/live/")
    print("    https://melbet-7626.pro/en/live/cricket/12345-Match")
    print()
    try:
        entered = input(f"  URL [default: {DEFAULT_URL}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        entered = ""

    if not entered:
        print(f"  → default ব্যবহার: {DEFAULT_URL}")
        return DEFAULT_URL

    # Add https:// if missing
    if not entered.startswith(("http://", "https://")):
        entered = "https://" + entered
        print(f"  → https:// যোগ করা হলো: {entered}")

    return entered


# ============================================================
#  Helpers
# ============================================================
def _now_tag():
    t = time.time()
    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime(t))
    ms = int((t % 1) * 1000)
    return ts, ms, t


def _sanitize_headers(h: dict) -> dict:
    out = {}
    for k, v in (h or {}).items():
        out[k] = "***REDACTED***" if k.lower() in REDACT_HEADERS else v
    return out


def _try_json(s):
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return s


def _wicket_subgames(data: dict) -> list:
    sgs = (data or {}).get("subGamesForMainGame") or []
    return [
        sg for sg in sgs
        if any(k in (sg.get("subGameName") or "").lower() for k in WICKET_KEYWORDS)
    ]


def _wicket_signature(wicket_sgs: list) -> tuple:
    rows = []
    for sg in wicket_sgs:
        sname = sg.get("subGameName") or ""
        for grp in (sg.get("eventGroups") or []):
            for ev in (grp.get("events") or []):
                rows.append(f"{sname}|t={ev.get('type')}|p={ev.get('parameter')}")
    return tuple(sorted(rows))


def _summarize(data: dict) -> list:
    out = []
    for sg in ((data or {}).get("subGamesForMainGame") or []):
        cnt = 0
        for grp in (sg.get("eventGroups") or []):
            cnt += len(grp.get("events") or [])
        out.append({"name": sg.get("subGameName"), "id": sg.get("id"), "events": cnt})
    return out


# ============================================================
#  ১) GameEvents response
# ============================================================
async def handle_game_events(resp):
    try:
        qs = parse_qs(urlparse(resp.url).query)
        gid = (qs.get("gameId") or [""])[0]
        if not gid:
            return

        if gid not in _seen_gids:
            _seen_gids.add(gid)
            print(f"🆕 gameId={gid} — capturing market feed…")

        try:
            data = await resp.json()
        except Exception:
            return
        if not isinstance(data, dict):
            return

        ts, ms, now = _now_tag()
        wsgs = _wicket_subgames(data)
        cur_sig = _wicket_signature(wsgs)
        prev_sig = _prev_wicket_sig.get(gid)
        changed = prev_sig is not None and cur_sig != prev_sig

        if changed and wsgs:
            wname = f"WICKET_CHANGE_{gid}_{ts}_{ms:03d}.json"
            (OUT_DIR / wname).write_text(
                json.dumps({
                    "captured_at": ts,
                    "gameId": gid,
                    "wicket_subgames": wsgs,
                    "all_subgame_names": [
                        sg.get("subGameName")
                        for sg in data.get("subGamesForMainGame", [])
                    ],
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"🚨 WICKET CHANGE → {wname}  ({len(wsgs)} wicket subGames)")

        _prev_wicket_sig[gid] = cur_sig

        if now - _last_save.get(gid, 0) < MIN_SAVE_INTERVAL:
            return
        _last_save[gid] = now

        fname = f"gameEvents_{gid}_{ts}_{ms:03d}.json"
        (OUT_DIR / fname).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        summ = _summarize(data)
        with (OUT_DIR / "summary.log").open("a", encoding="utf-8") as f:
            f.write(f"\n[{ts}.{ms:03d}] gid={gid} subgames={len(summ)} wicket={len(wsgs)}\n")
            for s in summ:
                f.write(f"   {s['name']!r} (id={s['id']}, events={s['events']})\n")

        print(f"💾 {fname}  (subgames={len(summ)}, wicket={len(wsgs)})")

    except Exception as e:
        print(f"⚠️ gameEvents: {type(e).__name__}: {e}")


# ============================================================
#  ২) Bet request + response
# ============================================================
async def handle_bet(resp):
    global _bet_count
    try:
        req = resp.request
        url_l = resp.url.lower()
        if "gameevents" in url_l:
            return

        is_bet = req.method == "POST" and any(h in url_l for h in BET_URL_HINTS)
        is_history = any(h in url_l for h in HISTORY_URL_HINTS)
        if not (is_bet or is_history):
            return

        ts, ms, _ = _now_tag()

        try:
            resp_data = await resp.json()
        except Exception:
            try:
                resp_data = await resp.text()
            except Exception:
                resp_data = None

        req_body = _try_json(req.post_data)

        bet_id = None
        err_code = None
        if isinstance(resp_data, dict):
            val = resp_data.get("Value") or {}
            if isinstance(val, dict):
                bet_id = val.get("Id") or val.get("BetId")
            bet_id = bet_id or resp_data.get("Id")
            err_code = resp_data.get("ErrorCode")
            if err_code is None:
                err_code = resp_data.get("Error")

        if is_bet:
            _bet_count += 1
            tag = f"BET_{_bet_count:03d}_{ts}_{ms:03d}_" \
                  f"{'OK' if bet_id else 'FAIL'}_{bet_id or 'noID'}.json"
        else:
            tag = f"HISTORY_{ts}_{ms:03d}.json"

        try:
            req_headers = _sanitize_headers(await req.all_headers())
        except Exception:
            req_headers = {}

        payload = {
            "captured_at": ts,
            "url": resp.url,
            "method": req.method,
            "request_headers": req_headers,
            "request_body": req_body,
            "response_status": resp.status,
            "response_body": resp_data,
            "parsed": {
                "bet_id": bet_id,
                "error_code": err_code,
                "success": bool(bet_id) and err_code in (0, None),
            },
        }

        (BETS_DIR / tag).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if is_bet:
            mark = "✅" if payload["parsed"]["success"] else "❌"
            print(f"💰 {mark} {tag}  (ErrorCode={err_code}, Id={bet_id})")
        else:
            print(f"📜 {tag}  ({len(str(resp_data))} chars)")

    except Exception as e:
        print(f"⚠️ bet: {type(e).__name__}: {e}")


async def on_response(resp):
    if "gameevents" in resp.url.lower():
        await handle_game_events(resp)
    else:
        await handle_bet(resp)


# ============================================================
#  Main
# ============================================================
async def main():
    print("=" * 68)
    print("  Melbet Payload Capture  —  Market + Bet")
    print("=" * 68)

    target_url = ask_url()

    print()
    print(f"🌐 Target URL:   {target_url}")
    print(f"📁 Output:       {OUT_DIR}")
    print(f"💰 Bets:         {BETS_DIR}")
    print(f"👤 Profile:      {PROFILE}")
    print()
    print("🔐 Sensitive headers (Cookie/Auth) redact করা হয়।")
    print()
    print("🧭 কী করবেন:")
    print("   1. Browser খুলবে → Melbet-এ লগইন করুন (না থাকলে)")
    print("   2. একটি লাইভ ম্যাচ খুলুন")
    print("   3. ২-৫ over কাটতে দিন (market feed capture হবে)")
    print("   4. ছোট stake-এ ১-২টি bet ধরুন (১৫-২০ টাকা)")
    print("      বিশেষত 'Fall of Xth Wicket' market-এ")
    print("   5. ১-২টি wicket পড়তে দিন (WICKET_CHANGE ফাইল তৈরি হবে)")
    print()
    print("   ⛔ বন্ধ করতে: Ctrl+C")
    print("=" * 68)
    print()

    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE),
            headless=False,
            channel="chrome",
            no_viewport=True,
            args=[
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-features=Translate",
            ],
        )

        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        tasks: set = set()

        def _spawn(coro):
            t = asyncio.create_task(coro)
            tasks.add(t)
            t.add_done_callback(tasks.discard)

        page.on("response", lambda r: _spawn(on_response(r)))

        try:
            print(f"🚀 Navigating to {target_url} …")
            await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
            print(f"✅ Loaded: {page.url}")
            print("   এখন Melbet-এ লগইন/ম্যাচ খুলুন।")
            print()
        except Exception as e:
            print(f"⚠️ Navigation failed: {type(e).__name__}: {e}")
            print("   ব্রাউজার খোলা আছে — নিজে navigate করুন।")
            print()

        try:
            while True:
                await asyncio.sleep(1)
                if page.is_closed():
                    print("🚪 Browser closed")
                    break
        except KeyboardInterrupt:
            print("\n👋 Exiting…")

        try:
            await ctx.close()
        except Exception:
            pass

    print(f"\n✅ Done.")
    print(f"   Market files: {OUT_DIR}")
    print(f"   Bet files:    {BETS_DIR}")
    print(f"   Total bets captured: {_bet_count}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass