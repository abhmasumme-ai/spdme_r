class BatsmanWorker:
    def __init__(self, engine, match_id):
        self.engine = engine
        self.match_id = match_id

    async def on_batsman_runs(self, striker_id=None, striker_name=None, line_value="31.5"):
        """Called by api_server on wicket events — bet Under on the striker's runs.

        striker_name: Entity থেকে আসা নাম (লাইভ ফ্লোতে এটাই ব্যবহার হয়)।
        striker_id:   শুধু Melbet-এর নিজস্ব playerId হলে দিন (যেমন run_batsman.py)।
                      Entity Sports-এর আইডি এখানে দেবেন না, দুটো আলাদা সিস্টেম।
        """
        return await self.process_wicket(
            striker_name=striker_name,
            striker_id=striker_id,
            line_value=line_value,
        )

    async def process_wicket(self, striker_name=None, striker_id=None, line_value="31.5"):
        label = striker_name or f"player_id={striker_id}"
        print(f"\n🏏 [Batsman Worker] Triggered! Striker: {label}")

        if not striker_name and not striker_id:
            print("⚠️ [Batsman] স্ট্রাইকার অজানা — বেট স্কিপ করা হলো।")
            return False

        game_events = await self.engine.get_latest_odds(self.match_id)
        if not game_events:
            print("⚠️ [Batsman] ওডস পাওয়া যায়নি।")
            return False

        market = self.engine.find_market(
            game_events,
            bet_type="under",
            line_value=line_value,
            player_name=striker_name,
            player_id=None if striker_name else striker_id,
        )

        if not market:
            print(f"⚠️ [Batsman] {label}-এর {line_value} Under মার্কেট পাওয়া যায়নি।")
            return False

        print(f"🎯 [Batsman] {label}-এর {line_value} Under বেট হচ্ছে... (সাবগেম: {market.get('subgame')})")
        ok = await self.engine.place_bet(
            market['game_id'], market['type'],
            market['coef'], market['param'],
            player_id=market.get('player_id', 0),
            match_id=self.match_id,
        )
        print(f"{'✅' if ok else '❌'} [Batsman] বেট ফলাফল: {'সফল' if ok else 'ব্যর্থ'}")
        return ok