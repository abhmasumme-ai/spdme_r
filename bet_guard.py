"""Bet safety guard — সব বেট place_bet-এর আগে এখান দিয়ে যায়।

- kill-switch: ON থাকলে কোনো বেট যাবে না
- ম্যাচ প্রতি সর্বোচ্চ বেট সংখ্যা ও মোট স্টেক (0 = সীমা নেই)
- ন্যূনতম odds
- delivery-প্রতি সর্বোচ্চ বেট (per category) — এক delivery-তে একই category-তে ২বার বেট আটকায়

asyncio একটাই থ্রেডে চলে, আর reserve() কোনো await ছাড়াই কোটা কেটে নেয়,
তাই একসাথে অনেক বেট এলেও সীমা পার হয় না।
"""
from config import MAX_BETS_PER_MATCH, MAX_STAKE_PER_MATCH, MIN_ODDS

try:
    from config import MAX_BETS_PER_DELIVERY
except ImportError:
    MAX_BETS_PER_DELIVERY = 1


class BetGuard:
    def __init__(self, max_bets, max_stake, min_odds, max_per_delivery=1):
        self.max_bets = max_bets
        self.max_stake = max_stake
        self.min_odds = min_odds
        self.max_per_delivery = max_per_delivery
        self.killed = False
        self._bets = {}
        self._staked = {}
        self._per_delivery = {}  # (match_key, delivery_key) -> count

    @staticmethod
    def _key(match_id):
        return str(match_id) if match_id else "global"

    def reserve(self, match_id, stake, coef, delivery_key=None):
        """বেটের আগে কোটা কাটে। (ok, কারণ) ফেরত দেয়।"""
        if self.killed:
            return False, "kill-switch চালু আছে"
        try:
            cf = float(coef)
        except (TypeError, ValueError):
            return False, f"odds অবৈধ ({coef!r})"
        if not cf >= self.min_odds:  # NaN-ও এখানে আটকায়
            return False, f"odds {coef} সর্বনিম্ন {self.min_odds}-এর কম"

        k = self._key(match_id)

        # Delivery-প্রতি সীমা
        if delivery_key and self.max_per_delivery:
            dk = (k, str(delivery_key))
            dn = self._per_delivery.get(dk, 0)
            if dn >= self.max_per_delivery:
                return False, f"delivery '{delivery_key}'-এ ইতিমধ্যে {dn}টি বেট"
        else:
            dk = None

        n = self._bets.get(k, 0)
        s = self._staked.get(k, 0)
        if self.max_bets and n >= self.max_bets:
            return False, f"ম্যাচ প্রতি সর্বোচ্চ বেট ({self.max_bets}) পূর্ণ"
        if self.max_stake and s + stake > self.max_stake:
            return False, f"ম্যাচ প্রতি সর্বোচ্চ স্টেক ({self.max_stake}) ছাড়িয়ে যাবে"

        self._bets[k] = n + 1
        self._staked[k] = s + stake
        if dk:
            self._per_delivery[dk] = self._per_delivery.get(dk, 0) + 1
        return True, ""

    def release(self, match_id, stake, delivery_key=None):
        """নিশ্চিত ব্যর্থ বেটের কোটা ফেরত দেয়।"""
        k = self._key(match_id)
        self._bets[k] = max(0, self._bets.get(k, 0) - 1)
        self._staked[k] = max(0, self._staked.get(k, 0) - stake)
        if delivery_key:
            dk = (k, str(delivery_key))
            self._per_delivery[dk] = max(0, self._per_delivery.get(dk, 0) - 1)

    def kill(self):
        self.killed = True

    def resume(self):
        self.killed = False

    def status(self):
        return {
            "killed": self.killed,
            "max_bets": self.max_bets,
            "max_stake": self.max_stake,
            "min_odds": self.min_odds,
            "max_per_delivery": self.max_per_delivery,
            "bets": dict(self._bets),
            "staked": dict(self._staked),
            "per_delivery": {f"{m}::{d}": c for (m, d), c in self._per_delivery.items()},
        }


guard = BetGuard(MAX_BETS_PER_MATCH, MAX_STAKE_PER_MATCH, MIN_ODDS, MAX_BETS_PER_DELIVERY)