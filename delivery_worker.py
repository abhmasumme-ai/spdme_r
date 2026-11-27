class DeliveryWorker:
    def __init__(self, engine, match_id):
        self.engine = engine
        self.match_id = match_id

    async def bet_same_delivery(self, entity_over, side, line, delivery_key=None):
        """
        Entity result-এর সাথে Melbet delivery মিললে bet place।
        delivery_key দিলে একই delivery-তে দ্বিতীয় bet guard আটকাবে।
        find_market ambiguous (>1 match) হলে কিছুই করবে না।
        """
        game_events = await self.engine.get_latest_odds(self.match_id)
        if not game_events:
            print("⚠️ [Delivery] Odds পাওয়া যায়নি")
            return False

        market = self.engine.find_market(
            game_events,
            bet_type=side,
            line_value=line,
            over_num=entity_over,
            require_unique=True,
        )
        if not market:
            print(f"⚠️ [Delivery] Over {entity_over} {line} {side.upper()} — "
                  f"no unique match (skip)")
            return False

        print(f"🎯 [Delivery] Bet: Over {entity_over} {line} {side.upper()} "
              f"(subgame='{market.get('subgame')}', coef={market.get('coef')})")

        ok = await self.engine.place_bet(
            market['game_id'], market['type'], market['coef'], market['param'],
            match_id=self.match_id,
            delivery_key=delivery_key,
        )
        print(f"{'✅' if ok else '❌'} [Delivery] Bet {'সফল' if ok else 'ব্যর্থ'}")
        return ok