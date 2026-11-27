class WicketWorker:
    def __init__(self, engine, match_id):
        self.engine = engine
        self.match_id = match_id

    async def on_wicket(self, line_value="1.5"):
        """Called by api_server on wicket events."""
        return await self.process_wicket(line_value=line_value)

    async def process_wicket(self, line_value="1.5"):
        print(f"\n🏏 [Wicket Worker] Fall in Wicket Triggered! (line={line_value})")
        game_events = await self.engine.get_latest_odds(self.match_id)
        if not game_events:
            print("⚠️ [Wicket] ওডস পাওয়া যায়নি।")
            return False

        market = self.engine.find_market(
            game_events, bet_type="wicket_under", line_value=line_value
        )

        if not market:
            print(f"⚠️ [Wicket] Fall in Wicket {line_value} Under মার্কেট পাওয়া যায়নি।")
            return False

        print(f"🎯 [Wicket] Fall in Wicket {line_value} Under বেট হচ্ছে...")
        ok = await self.engine.place_bet(
            market['game_id'], market['type'],
            market['coef'], market['param'],
            match_id=self.match_id,
        )
        print(f"{'✅' if ok else '❌'} [Wicket] বেট ফলাফল: {'সফল' if ok else 'ব্যর্থ'}")
        return ok