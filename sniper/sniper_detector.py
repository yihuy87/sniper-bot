# sniper/sniper_detector.py
# Deteksi pola Spike-Reversal (flush + rejection) tanpa indikator.

from typing import List, Dict, Optional, Literal

from binance.ohlc_buffer import Candle  # type alias dari project lama
from sniper.sniper_settings import sniper_settings


def _avg_body(candles: List[Candle], lookback: int = 20) -> float:
    sub = candles[-lookback:] if len(candles) > lookback else candles
    if not sub:
        return 0.0
    total = 0.0
    for c in sub:
        total += abs(c["close"] - c["open"])
    return total / len(sub)


def _count_side_candles(
    candles: List[Candle],
    side: Literal["bull", "bear"],
    lookback: int,
) -> int:
    sub = candles[-lookback:] if len(candles) > lookback else candles
    cnt = 0
    for c in sub:
        if side == "bull" and c["close"] > c["open"]:
            cnt += 1
        if side == "bear" and c["close"] < c["open"]:
            cnt += 1
    return cnt


def detect_spike_reversal(candles: List[Candle]) -> Optional[Dict]:
    """
    Deteksi 1 candle terakhir sebagai Spike-Reversal:

    LONG:
      - deretan candle merah sebelumnya (bearish leg)
      - last candle bullish besar (body >= factor * avg_body)
      - low candle terakhir < low minimum beberapa candle sebelumnya (flush)
      - close dekat high (rejection kuat dari bawah)

    SHORT:
      - kebalikan.
    """
    n = len(candles)
    if n < 25:
        return None

    last = candles[-1]
    prev = candles[-2]

    avg_body = _avg_body(candles[:-1], lookback=20)
    if avg_body <= 0:
        return None

    body_last = abs(last["close"] - last["open"])
    total_range = last["high"] - last["low"]
    if total_range <= 0:
        return None

    body_ratio = body_last / total_range

    # apakah candle terakhir cukup "impulsif"
    if body_last < sniper_settings.min_body_factor * avg_body:
        return None
    if body_ratio < sniper_settings.min_body_vs_range:
        return None

    # cek leg sebelumnya
    bear_leg_cnt = _count_side_candles(
        candles[:-1], "bear", sniper_settings.leg_lookback
    )
    bull_leg_cnt = _count_side_candles(
        candles[:-1], "bull", sniper_settings.leg_lookback
    )

    # sweep / flush: bandingkan high/low dengan window sebelumnya
    lookback_sweep = 15
    prev_segment = candles[-(lookback_sweep + 1):-1]
    if not prev_segment:
        return None

    prev_min_low = min(c["low"] for c in prev_segment)
    prev_max_high = max(c["high"] for c in prev_segment)

    side: Optional[str] = None
    sweep_ok = False

    # --- kandidat LONG ---
    if (
        last["close"] > last["open"]          # bullish
        and bear_leg_cnt >= sniper_settings.min_bear_candles
        and last["low"] < prev_min_low       # flush low lebih dalam
    ):
        # close dekat high → rejection kuat
        upper_wick = last["high"] - max(last["open"], last["close"])
        wick_ratio = upper_wick / total_range
        # kita mau upper wick kecil, lower wick panjang (reversal naik)
        if wick_ratio <= 0.25:
            side = "long"
            sweep_ok = True

    # --- kandidat SHORT ---
    if side is None and (
        last["close"] < last["open"]          # bearish
        and bull_leg_cnt >= sniper_settings.min_bull_candles
        and last["high"] > prev_max_high
    ):
        lower_wick = min(last["open"], last["close"]) - last["low"]
        wick_ratio = lower_wick / total_range
        if wick_ratio <= 0.25:
            side = "short"
            sweep_ok = True

    if side is None:
        return None

    return {
        "side": side,
        "sweep_ok": sweep_ok,
        "body": body_last,
        "range": total_range,
        "bear_leg_cnt": bear_leg_cnt,
        "bull_leg_cnt": bull_leg_cnt,
        "last": last,
    }
