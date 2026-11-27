import asyncio
from patchright.async_api import async_playwright
from melbet_engine import MelbetEngine
from batsman_worker import BatsmanWorker

MELBET_URL = "https://melbet-7626.pro"
STRIKER_ID = 219547144
LINE_VALUE = "31.5"
current_match_id = None

async def on_request(req):
    global current_match_id
    if "gameEvents" in req.url and "gameId=" in req.url:
        try:
            gid = req.url.split("gameId=")[1].split("&")[0]
            if gid != current_match_id:
                current_match_id = gid
                print(f"\n🎯 Match GameId ধরা পড়েছে: {current_match_id}")
        except: pass

async def async_input(prompt):
    return await asyncio.get_running_loop().run_in_executor(None, input, prompt)

async def main():
    global current_match_id
    pw = await async_playwright().start()
    ctx = await pw.chromium.launch_persistent_context(
        user_data_dir="./profile_batsman", headless=False, channel="chrome", no_viewport=True, args=["--start-maximized"]
    )
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    page.on("request", lambda r: asyncio.create_task(on_request(r)))

    print("🌐 [BATSMAN] ব্রাউজার ওপেন হচ্ছে...")
    await page.goto(MELBET_URL)

    print("\n👉 ১) লগইন করুন\n👉 ২) ম্যাচ ওপেন করুন\n👉 ৩) 'done' লিখে Enter দিন")

    engine = MelbetEngine(page)
    worker = None

    while True:
        cmd = (await async_input("\n👉 [BATSMAN] Command (done/q): ")).strip().lower()
        if cmd in ("done", "batsman done"):
            if not current_match_id:
                print("❌ ম্যাচ আইডি নেই!")
                continue
            if worker is None: worker = BatsmanWorker(engine, current_match_id)
            else: worker.match_id = current_match_id
            print(f"⚡ [BATSMAN] বেট ফায়ার (Line: {LINE_VALUE})...")
            await worker.on_batsman_runs(striker_id=STRIKER_ID, line_value=LINE_VALUE)
        elif cmd in ("q", "quit", "exit"):
            break

    await ctx.close()
    await pw.stop()

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: print("\n🛑 বন্ধ।")