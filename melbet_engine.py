import asyncio
import re

from bet_guard import guard
from config import BET_STAKE
from runtime_config import runtime


class MelbetEngine:
    DEFAULT_OVER_TYPES = {2066}
    DEFAULT_UNDER_TYPES = {2067}
    DEFAULT_WICKET_UNDER_TYPES = {13523}

    def __init__(self, page):
        self.page = page
        self.partner = 8
        self.group = 1184
        self.user_id = 0
        self._learned_over_types = set()
        self._learned_under_types = set()
        self._learned_wicket_under_types = set()

    async def get_user_id(self):
        if self.user_id != 0:
            return self.user_id
        js = "() => { try { return parseInt(localStorage.getItem('userId')); } catch(e) { return 0; } }"
        try:
            uid = await self.page.evaluate(js)
            if uid and uid > 0:
                self.user_id = uid
        except Exception:
            pass
        return self.user_id

    async def get_latest_odds(self, match_game_id):
        url = (
            f"/service-api/main-live-feed/v3/gameEvents"
            f"?cfView=3&countEvents=250&fcountry=19&gameId={match_game_id}"
            f"&gr=1184&grMode=4&lng=en&marketType=1"
        )
        js_fetch = "async (url) => { const res = await fetch(url); return await res.json(); }"
        try:
            return await self.page.evaluate(js_fetch, url)
        except Exception as e:
            print(f"❌ Odds fetch error: {e}")
            return None

    async def get_current_over(self, match_id):
        """Melbet feed থেকে বর্তমান Entity-সামঞ্জস্য over বের করে।"""
        game_events = await self.get_latest_odds(match_id)
        if not game_events:
            return None
        highest_melbet = 0
        for sg in game_events.get("subGamesForMainGame", []):
            name = (sg.get("subGameName") or "").lower()
            m = re.search(r'\bover\s+(\d+)', name)
            if m:
                n = int(m.group(1))
                if n > highest_melbet:
                    highest_melbet = n
        if highest_melbet == 0:
            return None
        return highest_melbet - 1

    @staticmethod
    def _iter_events(events_field):
        if not events_field:
            return
        if isinstance(events_field, list) and events_field and isinstance(events_field[0], dict):
            for ev in events_field:
                if isinstance(ev, dict):
                    yield ev
        else:
            for group_list in events_field:
                if isinstance(group_list, list):
                    for ev in group_list:
                        if isinstance(ev, dict):
                            yield ev
                elif isinstance(group_list, dict):
                    yield group_list

    @staticmethod
    def _clean_num(v):
        s = str(v)
        return s.rstrip("0").rstrip(".") if "." in s else s

    @staticmethod
    def _param_strings(event):
        clean = MelbetEngine._clean_num
        ep = event.get("eventParams")
        raw = ep.get("params", []) if isinstance(ep, dict) else []
        out = set()
        if isinstance(raw, list):
            for v in raw:
                if isinstance(v, (str, int, float)):
                    out.add(str(v))
                    out.add(clean(v))
                elif isinstance(v, dict):
                    for vv in v.values():
                        if isinstance(vv, (str, int, float)):
                            out.add(str(vv))
                            out.add(clean(vv))
        for k in ("parameter", "param", "line", "handicap"):
            v = event.get(k)
            if isinstance(v, (str, int, float)):
                out.add(str(v))
                out.add(clean(v))
        return out

    @staticmethod
    def _normalize_number_str(s):
        try:
            f = float(s)
            if f == int(f):
                return str(int(f))
            return f"{f:.4f}".rstrip("0").rstrip(".")
        except (TypeError, ValueError):
            return s

    def _match_param(self, params_set, target):
        if target is None:
            return True
        want = self._normalize_number_str(str(target))
        for p in params_set:
            if self._normalize_number_str(p) == want:
                return True
        return False

    def _over_matches(self, params_set, over_num_entity):
        if over_num_entity is None:
            return True
        melbet_over = over_num_entity + 1
        candidates = {
            str(melbet_over), f"{melbet_over}.0",
            f"Over {melbet_over}", f"over {melbet_over}", f"OVER {melbet_over}",
        }
        for p in params_set:
            ps = str(p).strip()
            if ps in candidates:
                return True
            low = ps.lower()
            if low.startswith("over"):
                try:
                    n = int(re.findall(r"\d+", low)[0])
                    if n == melbet_over:
                        return True
                except (IndexError, ValueError):
                    pass
        return False

    def _over_matches_by_name(self, subgame_name, params_set, over_num_entity):
        if over_num_entity is None:
            return True
        melbet_over = over_num_entity + 1
        sn = (subgame_name or "").lower()
        m = re.search(r'\bover\s+(\d+)', sn)
        if m:
            return int(m.group(1)) == melbet_over
        return self._over_matches(params_set, over_num_entity)

    @staticmethod
    def _norm_name(s):
        s = re.sub(r"[^a-z\s]", " ", (s or "").lower())
        return " ".join(s.split())

    @classmethod
    def name_matches(cls, player_name, subgame_name):
        p = cls._norm_name(player_name)
        g = cls._norm_name(subgame_name)
        if not p:
            return True
        if p in g:
            return True
        parts = p.split()
        if len(parts) >= 2:
            first, last = parts[0], parts[-1]
            toks = g.split()
            for i, t in enumerate(toks):
                if t == last and i > 0:
                    prev = toks[i - 1]
                    if prev == first or (len(prev) == 1 and prev == first[0]):
                        return True
        return False

    @staticmethod
    def _infer_group_kind(subgame_name: str) -> dict:
        n = (subgame_name or "").lower()
        return {
            "is_wicket": any(k in n for k in (
                "wicket", "fall of wicket", "fow", "1st wicket", "total wickets",
            )),
            "is_batsman": any(k in n for k in (
                "batsman", "batter", "player", "individual",
            )),
            "is_over_under": any(k in n for k in (
                "over", "runs", "total", "handicap", "line",
            )),
        }

    def _remember_type(self, bet_type, ev_type):
        if bet_type == "over":
            self._learned_over_types.add(ev_type)
        elif bet_type == "under":
            self._learned_under_types.add(ev_type)
        elif bet_type == "wicket_under":
            self._learned_wicket_under_types.add(ev_type)

    def _candidate_over_types(self):
        return (self._learned_over_types or self.DEFAULT_OVER_TYPES) | self.DEFAULT_OVER_TYPES

    def _candidate_under_types(self):
        return (self._learned_under_types or self.DEFAULT_UNDER_TYPES) | self.DEFAULT_UNDER_TYPES

    def _candidate_wicket_under_types(self):
        return (self._learned_wicket_under_types or self.DEFAULT_WICKET_UNDER_TYPES) | self.DEFAULT_WICKET_UNDER_TYPES

    def find_market(self, game_events_data, bet_type, line_value=None,
                    over_num=None, player_name=None, player_id=None,
                    verbose=False, require_unique=True):
        if not game_events_data or "subGamesForMainGame" not in game_events_data:
            return None

        candidates_types = (
            self._candidate_over_types() if bet_type == "over"
            else self._candidate_wicket_under_types() if bet_type == "wicket_under"
            else self._candidate_under_types()
        )

        matches = []
        debug_rows = []

        for subgame in game_events_data["subGamesForMainGame"]:
            game_id = subgame.get("id")
            subgame_name = subgame.get("subGameName", "") or ""
            kinds = self._infer_group_kind(subgame_name)

            if player_name and not self.name_matches(player_name, subgame_name):
                continue
            if bet_type == "wicket_under" and not kinds["is_wicket"]:
                continue
            if bet_type == "under" and player_name and not kinds["is_batsman"]:
                continue

            for group in subgame.get("eventGroups", []):
                for event in self._iter_events(group.get("events", [])):
                    ev_type = event.get("type")
                    if ev_type is None:
                        continue

                    params_set = self._param_strings(event)

                    if verbose:
                        debug_rows.append({
                            "sg": subgame_name, "type": ev_type,
                            "param": event.get("parameter"),
                            "params": sorted(params_set),
                            "cf": event.get("cf"),
                        })

                    if ev_type not in candidates_types:
                        continue

                    if player_id:
                        ev_pid = event.get("playerId", 0)
                        try:
                            if not ev_pid or int(ev_pid) != int(player_id):
                                continue
                        except (TypeError, ValueError):
                            continue

                    if line_value is not None and not self._match_param(params_set, line_value):
                        continue

                    if bet_type in ("over", "under") and over_num is not None and not player_name:
                        if not self._over_matches_by_name(subgame_name, params_set, over_num):
                            continue

                    matches.append({
                        "game_id": game_id,
                        "type": ev_type,
                        "param": event.get("parameter"),
                        "coef": event.get("cf"),
                        "player_id": event.get("playerId", 0),
                        "params": sorted(params_set),
                        "subgame": subgame_name,
                    })

                    if require_unique and len(matches) > 1:
                        print(f"⚠️ [find_market] AMBIGUOUS: '{bet_type}' line={line_value} "
                              f"over={over_num} — {len(matches)}+ matches. Skip.")
                        return None

        if not matches:
            if verbose:
                print(f"🔍 [find_market] No match. bet={bet_type} line={line_value} "
                      f"over_entity={over_num} types={sorted(candidates_types)}")
            return None

        if require_unique and len(matches) > 1:
            print(f"⚠️ [find_market] AMBIGUOUS: {len(matches)} matches. Skip.")
            return None

        result = matches[0]
        self._remember_type(bet_type, result["type"])
        return result

    def find_player_under(self, game_events_data, player_name, line_value,
                          require_unique=True):
        if not game_events_data or "subGamesForMainGame" not in game_events_data:
            return None

        matches = []
        for subgame in game_events_data["subGamesForMainGame"]:
            subgame_name = subgame.get("subGameName", "") or ""
            if not player_name or not self.name_matches(player_name, subgame_name):
                continue
            sn_lower = subgame_name.lower()
            if not any(k in sn_lower for k in ("run", "batsman", "player", "individual")):
                continue

            for group in subgame.get("eventGroups", []):
                for event in self._iter_events(group.get("events", [])):
                    ev_type = event.get("type")
                    if ev_type is None:
                        continue
                    params_set = self._param_strings(event)
                    if not self._match_param(params_set, line_value):
                        continue

                    matches.append({
                        "game_id": subgame.get("id"),
                        "type": ev_type,
                        "param": event.get("parameter"),
                        "coef": event.get("cf"),
                        "player_id": event.get("playerId", 0),
                        "subgame": subgame_name,
                    })

                    if require_unique and len(matches) > 1:
                        print(f"⚠️ [find_player_under] AMBIGUOUS: '{player_name}' "
                              f"line={line_value} — {len(matches)}+ matches. Skip.")
                        return None

        if not matches:
            return None
        if require_unique and len(matches) > 1:
            return None
        return matches[0]

    def discover_types(self, game_events_data):
        seen = {}
        if not game_events_data or "subGamesForMainGame" not in game_events_data:
            return seen
        for sg in game_events_data["subGamesForMainGame"]:
            name = sg.get("subGameName", "")
            for grp in sg.get("eventGroups", []):
                for ev in self._iter_events(grp.get("events", [])):
                    t = ev.get("type")
                    if t is None:
                        continue
                    key = (name, t)
                    if key not in seen:
                        seen[key] = {
                            "param": ev.get("parameter"),
                            "params": sorted(self._param_strings(ev)),
                            "cf": ev.get("cf"),
                        }
        return seen

    async def place_bet(self, game_id, bet_type, coef, param, stake=None,
                        player_id=0, match_id=None, delivery_key=None):
        """
        stake=None হলে runtime.stake ব্যবহার হবে (UI থেকে dynamic)।
        delivery_key দিলে একই delivery-তে দ্বিতীয় bet guard আটকাবে।
        """
        if stake is None:
            stake = runtime.stake
        uid = await self.get_user_id()
        if uid == 0:
            print("❌ User ID পাওয়া যায়নি! লগইন চেক করুন।")
            return False

        ok, reason = guard.reserve(match_id, stake, coef, delivery_key=delivery_key)
        if not ok:
            print(f"🛑 বেট আটকানো হয়েছে: {reason}")
            return False

        api_url = "/service-api/LiveBet/Secure/MakeBetWeb"
        payload = {
            "UserId": uid,
            "Events": [{
                "GameId": game_id, "Type": bet_type, "Coef": coef, "Param": param,
                "PV": None, "PlayerId": player_id, "Kind": 1, "InstrumentId": 0,
                "Seconds": 0, "Price": 0, "Expired": 0, "PlayersDuel": [],
            }],
            "Vid": 0, "partner": self.partner, "Group": self.group,
            "live": True, "CheckCf": 1, "Lng": "en", "notWait": True,
            "IsPowerBet": False, "Summ": stake, "Source": 55, "OneClickBet": 1,
        }

        js_fetch = """
        async (args) => {
            const res = await fetch(args.url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(args.payload) });
            return { status: res.status, data: await res.json() };
        }
        """

        outcome = "unknown"
        try:
            for _ in range(3):
                try:
                    res = await self.page.evaluate(js_fetch, {"url": api_url, "payload": payload})
                except Exception as e:
                    print(f"❌ Bet eval failed: {e}")
                    return False

                res = res if isinstance(res, dict) else {}
                data = res.get("data") if isinstance(res.get("data"), dict) else {}
                if res.get("status") == 200 and data.get("ErrorCode") == 0:
                    value = data.get("Value") if isinstance(data.get("Value"), dict) else {}
                    if (value.get("Id") or 0) > 0:
                        outcome = "ok"
                        print(f"✅ বেট সফল! ID: {value['Id']} | Stake: {stake}")
                        return True
                    if value.get("betGUID"):
                        payload["betGUID"] = value["betGUID"]
                        await asyncio.sleep(0.3)
                        continue
                outcome = "failed"
                print(f"❌ বেট ফেইল: status={res.get('status')} ErrorCode={data.get('ErrorCode')}")
                return False
            print("❌ বেট কনফার্ম হয়নি।")
            return False
        finally:
            if outcome == "failed":
                guard.release(match_id, stake, delivery_key=delivery_key)