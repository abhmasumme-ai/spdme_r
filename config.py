import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


# ============================================================
#  Entity Sports — keys (ES_* আগে, তারপর ENTITY_* fallback)
# ============================================================
ENTITY_REST_TOKEN = (
    os.getenv("ES_REST_TOKEN", "").strip()
    or os.getenv("ENTITY_API_TOKEN", "").strip()
)

ENTITY_REST_BASE = (
    os.getenv("ES_REST_BASE", "").strip()
    or os.getenv("ENTITY_REST_BASE", "https://restapi.entitysport.com/v2").strip()
).rstrip("/")

ENTITY_PUSH_TOKEN = (
    os.getenv("ES_PUSH_TOKEN", "").strip()
    or os.getenv("ENTITY_PUSH_TOKEN", "").strip()
)

ENTITY_PUSH_URL = (
    os.getenv("ES_PUSH_URL", "").strip()
    or os.getenv("ENTITY_PUSH_URL", "").strip()
)

ENTITY_PUSH_INSECURE_SSL = os.getenv(
    "ENTITY_PUSH_INSECURE_SSL", "false"
).lower() in ("1", "true", "yes", "on")


def get_entity_token(force_refresh: bool = False) -> str:
    if not ENTITY_REST_TOKEN:
        raise RuntimeError("ES_REST_TOKEN / ENTITY_API_TOKEN .env-এ সেট করা নেই")
    return ENTITY_REST_TOKEN


# backward-compat
ENTITY_API_TOKEN = ENTITY_REST_TOKEN


# ============================================================
#  Exchange tuning
# ============================================================
EXCHANGE_MAX_COMPETITIONS = int(os.getenv("EXCHANGE_MAX_COMPETITIONS", "5"))
EXCHANGE_CACHE_TTL = int(os.getenv("EXCHANGE_CACHE_TTL", "20"))


# ============================================================
#  Betting limits (bet_guard.py এগুলো import করে)
# ============================================================
BET_STAKE = float(os.getenv("BET_STAKE", "15"))
CHECK_CF = int(os.getenv("CHECK_CF", "0"))
MIN_ODDS = float(os.getenv("MIN_ODDS", "1.10"))
MAX_BETS_PER_MATCH = int(os.getenv("MAX_BETS_PER_MATCH", "15"))
MAX_STAKE_PER_MATCH = float(os.getenv("MAX_STAKE_PER_MATCH", "0"))
MAX_BETS_PER_DELIVERY = int(os.getenv("MAX_BETS_PER_DELIVERY", "1"))


# ============================================================
#  Lines / runtime
# ============================================================
DELIVERY_DOT_LINE = float(os.getenv("DELIVERY_DOT_LINE", "0.5"))
DELIVERY_FOUR_LINE = float(os.getenv("DELIVERY_FOUR_LINE", "3.5"))
BATSMAN_LINE = float(os.getenv("BATSMAN_LINE", "31.5"))
WICKET_LINE = float(os.getenv("WICKET_LINE", "1.5"))
ODDS_POLL_INTERVAL = float(os.getenv("ODDS_POLL_INTERVAL", "0.35"))


OVER_ZERO_IS_LAST_BALL = os.getenv(
    "OVER_ZERO_IS_LAST_BALL", "false"
).lower() in ("1", "true", "yes", "on")


def profile_dir(name: str) -> str:
    p = BASE_DIR / f"profile_{name}"
    p.mkdir(exist_ok=True)
    return str(p)