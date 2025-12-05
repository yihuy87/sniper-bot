# sniper/sniper_analyzer.py
# Ubah hasil deteksi Spike-Reversal menjadi sinyal lengkap Entry/SL/TP/Leverage.

from typing import List, Dict, Optional

from binance.ohlc_buffer import Candle
from sniper.sniper_detector import detect_spike_reversal
from sniper.sniper_settings import sniper_settings
from sniper.sniper_tiers import evaluate_signal_quality
from common.htf_context import get_htf_context

# cooldown per symbol (berdasarkan jumlah candle yang sudah close)
_last_signal_len: Dict[str, int] = {}


def _build_levels(side: str, last: Candle) -> Dict[str, float]:
    """
    Entry dekat bawah/atas tubuh candle spike,
    SL di luar wick sedikit, TP multi-RR.
    """
    low = last["low"]
    high = last["high"]
    open_ = last["open"]
    close = last["close"]

    mid_body = 0.5 * (open_ + close)
    rng = max(high - low, 1e-9)

    if side == "long":
        # entry dekat 20% dari low ke body-mid (lebih dekat ke bawah)
        entry = low + 0.2 * (mid_body - low)
        # SL sedikit di bawah low
        sl = low - 0.15 * rng
        risk = entry - sl
        tp1 = entry + 1.5 * risk
        tp2 = entry + 2.2 * risk
        tp3 = entry + 3.0 * risk
    else:
        entry = high - 0.2 * (high - mid_body)
        sl = high + 0.15 * rng
        risk = sl - entry
        tp1 = entry - 1.5 * risk
        tp2 = entry - 2.2 * risk
        tp3 = entry - 3.0 * risk

    if risk <= 0:
        risk = abs(entry) * 0.003
        if side == "long":
            sl = entry - risk
        else:
            sl = entry + risk

    sl_pct = abs(risk / entry) * 100.0 if entry != 0 else 0.0

    # leverage dinamis sederhana
    if sl_pct <= 0.0:
        lev_min, lev_max = 5.0, 10.0
    elif sl_pct <= 0.25:
        lev_min, lev_max = 20.0, 30.0
    elif sl_pct <= 0.40:
        lev_min, lev_max = 15.0, 25.0
    elif sl_pct <= 0.70:
        lev_min, lev_max = 8.0, 15.0
    elif sl_pct <= 1.20:
        lev_min, lev_max = 5.0, 8.0
    else:
        lev_min, lev_max = 3.0, 5.0

    return {
        "entry": float(entry),
        "sl": float(sl),
        "tp1": float(tp1),
        "tp2": float(tp2),
        "tp3": float(tp3),
        "sl_pct": float(sl_pct),
        "lev_min": float(lev_min),
        "lev_max": float(lev_max),
    }


def analyze_symbol_sniper(symbol: str, candles_5m: List[Candle]) -> Optional[Dict]:
    """
    Analisa 5m untuk strategi Sniper Reversal.
    Dipanggil sekali setiap candle 5m close per symbol.
    """
    n = len(candles_5m)
    if n < 25:
        return None

    # cooldown per pair
    last_len = _last_signal_len.get(symbol)
    if last_len is not None:
        if n - last_len < sniper_settings.cooldown_candles:
            return None

    det = detect_spike_reversal(candles_5m)
    if not det:
        return None

    side = det["side"]
    last = det["last"]

    levels = _build_levels(side, last)
    entry = levels["entry"]
    sl = levels["sl"]
    tp1 = levels["tp1"]
    tp2 = levels["tp2"]
    tp3 = levels["tp3"]
    sl_pct = levels["sl_pct"]
    lev_min = levels["lev_min"]
    lev_max = levels["lev_max"]

    # cek RR TP2
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    rr_tp2 = abs(tp2 - entry) / risk
    good_rr = rr_tp2 >= sniper_settings.min_rr_tp2

    if sl_pct <= 0 or sl_pct > sniper_settings.max_sl_pct:
        return None

    # HTF context (reuse dari IMB)
    htf_ctx = get_htf_context(symbol)
    if side == "long":
        htf_ok = bool(htf_ctx.get("htf_ok_long", True))
    else:
        htf_ok = bool(htf_ctx.get("htf_ok_short", True))

    has_leg = (
        det["bear_leg_cnt"] >= sniper_settings.min_bear_candles
        or det["bull_leg_cnt"] >= sniper_settings.min_bull_candles
    )
    spike_ok = True
    sweep_ok = bool(det["sweep_ok"])

    meta = {
        "has_leg": has_leg,
        "spike_ok": spike_ok,
        "sweep_ok": sweep_ok,
        "htf_ok": htf_ok,
        "good_rr": good_rr,
        "sl_pct": sl_pct,
    }

    q = evaluate_signal_quality(meta)
    if not q["should_send"]:
        return None

    tier = q["tier"]
    score = q["score"]

    direction_label = "LONG" if side == "long" else "SHORT"
    emoji = "🟢" if side == "long" else "🔴"

    sl_pct_text = f"{sl_pct:.2f}%"
    lev_text = f"{lev_min:.0f}x–{lev_max:.0f}x"

    max_age_candles = sniper_settings.max_entry_age_candles
    approx_minutes = max_age_candles * 5
    valid_text = f"±{approx_minutes} menit" if approx_minutes > 0 else "singkat"

    # Risk calculator mini
    if sl_pct > 0:
        pos_mult = 100.0 / sl_pct
        example_balance = 100.0
        example_pos = pos_mult * example_balance
        risk_calc = (
            f"Risk Calc (contoh risiko 1%):\n"
            f"• SL : {sl_pct_text} → nilai posisi ≈ (1% / SL%) × balance ≈ {pos_mult:.1f}× balance\n"
            f"• Contoh balance 100 USDT → posisi ≈ {example_pos:.0f} USDT\n"
            f"(sesuaikan dengan balance & leverage kamu)"
        )
    else:
        risk_calc = "Risk Calc: SL% tidak valid (0), abaikan kalkulasi ini."

    text = (
        f"{emoji} SNIPER SIGNAL — {symbol.upper()} ({direction_label})\n"
        f"Entry : `{entry:.6f}`\n"
        f"SL    : `{sl:.6f}`\n"
        f"TP1   : `{tp1:.6f}`\n"
        f"TP2   : `{tp2:.6f}`\n"
        f"TP3   : `{tp3:.6f}`\n"
        f"Model : Spike-Reversal Sniper\n"
        f"Rekomendasi Leverage : {lev_text} (SL {sl_pct_text})\n"
        f"Validitas Entry : {valid_text}\n"
        f"Tier : {tier} (Score {score})\n"
        f"{risk_calc}"
    )

    _last_signal_len[symbol] = n

    return {
        "symbol": symbol.upper(),
        "side": side,
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "sl_pct": sl_pct,
        "lev_min": lev_min,
        "lev_max": lev_max,
        "tier": tier,
        "score": score,
        "htf_context": htf_ctx,
        "message": text,
    }
