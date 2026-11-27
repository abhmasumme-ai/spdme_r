import re


_WICKET_TOKENS = ("w", "wicket", "out", "bowled", "lbw", "caught",
                  "stumped", "run out", "runout", "hit wicket")
_WIDE_TOKENS = ("wd", "wide")
_NOBALL_TOKENS = ("nb", "noball", "no ball", "no-ball")


def classify_ball_result(ev, ball_data=None):
    """
    Ball result শ্রেণিবদ্ধ করে structured dict রিটার্ন করে।
    Pre-ball ("Ball Chalu") → None।
    """
    ball_data = ball_data or {}
    ev_lower = str(ev or "").strip().lower()

    if ev_lower in ("ball chalu", "ball start", "ball started"):
        return None

    def _int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    bat_run = _int(ball_data.get("bat_run"))
    wide_run = _int(ball_data.get("wide_run"))
    noball_run = _int(ball_data.get("noball_run"))
    bye_run = _int(ball_data.get("bye_run"))
    legbye_run = _int(ball_data.get("legbye_run"))

    is_wicket = any(t in ev_lower for t in _WICKET_TOKENS) or ev_lower == "w"
    is_wide = any(t in ev_lower for t in _WIDE_TOKENS)
    is_noball = any(t in ev_lower for t in _NOBALL_TOKENS)

    # Priority: run field from data (already total)
    total_runs = _int(ball_data.get("run"))
    if total_runs == 0 and not (is_wide or is_noball or bat_run or bye_run or legbye_run):
        # Maybe bat_run itself is total
        total_runs = bat_run + bye_run + legbye_run
    if total_runs == 0 and ev_lower.isdigit():
        total_runs = int(ev_lower)
        bat_run = total_runs

    if is_wicket:
        kind = "wicket"
    elif is_wide:
        kind = "wide"
    elif is_noball:
        kind = "noball"
    elif total_runs == 0:
        kind = "dot"
    elif total_runs == 4:
        kind = "four"
    elif total_runs == 6:
        kind = "six"
    else:
        kind = "run"

    return {
        "kind": kind,
        "total_runs": total_runs,
        "bat_run": bat_run,
        "wide_run": wide_run,
        "noball_run": noball_run,
        "bye_run": bye_run,
        "legbye_run": legbye_run,
        "is_wicket": is_wicket,
        "is_wide": is_wide,
        "is_noball": is_noball,
    }


def pick_bet_side_and_line(total_runs, is_wicket, is_wide=False, is_noball=False):
    """
    Entity result → (side, line) mapping। None মানে skip।

    Mapping:
        dot(0) / W                       → ("under", "0.5")
        1 / wide / noball                → ("over",  "0.5")
        2, 3 / wide+2, wide+3 / nb+1..2  → ("over",  "1.5")
        4, 6 / wide+4+ / nb+4+           → ("over",  "3.5")
    """
    if is_wicket or total_runs == 0:
        return ("under", "0.5")
    if total_runs == 1:
        return ("over", "0.5")
    if is_wide:
        if total_runs in (2, 3, 4):
            return ("over", "1.5")
        return ("over", "3.5")
    if is_noball:
        if total_runs in (2, 3):
            return ("over", "1.5")
        return ("over", "3.5")
    if total_runs in (2, 3):
        return ("over", "1.5")
    return ("over", "3.5")


def classify_entity_event(ev):
    """Backward-compat। UI log/generic ব্যবহারের জন্য।"""
    r = classify_ball_result(ev)
    if r is None:
        return "intermediate"
    if r["is_wicket"]:
        return "wicket"
    if r["kind"] == "dot":
        return "dot"
    if r["kind"] == "four":
        return "four"
    if r["kind"] == "six":
        return "six"
    if r["kind"] == "run":
        return "run"
    if r["kind"] in ("wide", "noball"):
        return "other"
    return "intermediate"