# sniper/sniper_tiers.py
# Skoring kualitas sinyal & penentuan Tier (A+, A, B, NONE).

from typing import Dict
from core.bot_state import state
from sniper.sniper_settings import sniper_settings


def score_signal(meta: Dict) -> int:
    """
    meta:
    {
      "has_leg": bool,
      "spike_ok": bool,
      "sweep_ok": bool,
      "htf_ok": bool,
      "good_rr": bool,
      "sl_pct": float,
    }
    """
    score = 0

    if meta.get("has_leg"):
        score += 20
    if meta.get("spike_ok"):
        score += 30
    if meta.get("sweep_ok"):
        score += 15
    if meta.get("htf_ok"):
        score += 15
    if meta.get("good_rr"):
        score += 10

    sl_pct = float(meta.get("sl_pct", 0.0))
    if 0.10 <= sl_pct <= sniper_settings.max_sl_pct:
        score += 10

    return int(min(score, 150))


def tier_from_score(score: int) -> str:
    if score >= 120:
        return "A+"
    elif score >= 100:
        return "A"
    elif score >= 80:
        return "B"
    else:
        return "NONE"


def should_send_tier(tier: str) -> bool:
    """
    Bandingkan tier dengan minimal tier (dari bot_state atau default sniper_settings).
    """
    order = {"NONE": 0, "B": 1, "A": 2, "A+": 3}
    min_tier = state.min_tier or sniper_settings.default_min_tier
    return order.get(tier, 0) >= order.get(min_tier, 2)


def evaluate_signal_quality(meta: Dict) -> Dict:
    score = score_signal(meta)
    tier = tier_from_score(score)

    sl_pct = float(meta.get("sl_pct", 0.0))
    spike_ok = bool(meta.get("spike_ok"))
    htf_ok = bool(meta.get("htf_ok"))
    good_rr = bool(meta.get("good_rr"))

    hard_ok = True

    if not spike_ok:
        hard_ok = False
    if not htf_ok:
        hard_ok = False
    if not good_rr:
        hard_ok = False
    if not (0.10 <= sl_pct <= sniper_settings.max_sl_pct):
        hard_ok = False

    should_send = should_send_tier(tier) and hard_ok

    return {
        "score": score,
        "tier": tier,
        "should_send": should_send,
    }
