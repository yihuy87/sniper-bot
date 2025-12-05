# sniper/sniper_settings.py
# Pengaturan utama untuk strategi Sniper Reversal.

from dataclasses import dataclass


@dataclass
class SniperSettings:
    # --- Scanner / pairs ---
    max_pairs: int = 400                 # berapa pair di-scan
    min_volume_usdt: float = 5_000_000   # filter volume 24h

    # --- Candle / leg context ---
    leg_lookback: int = 18               # panjang leg untuk cek tren pendek
    min_bear_candles: int = 6            # min candle merah di leg turun (untuk long)
    min_bull_candles: int = 6            # min candle hijau di leg naik (untuk short)

    # --- Spike strength ---
    min_body_factor: float = 2.0         # body spike >= 2x rata-rata body
    min_body_vs_range: float = 0.55      # body / (high-low) min 55%

    # --- SL & RR ---
    max_sl_pct: float = 0.80             # SL% maksimal yang masih diterima
    min_rr_tp2: float = 1.6              # RR minimal di TP2

    # --- Cooldown ---
    cooldown_candles: int = 3            # minimal jeda candle antar sinyal per pair

    # --- Validitas pesan ---
    max_entry_age_candles: int = 6       # untuk teks "validitas entry"

    # --- Tier minimal default (boleh di-override dari Telegram lewat bot_state) ---
    default_min_tier: str = "A"          # A+ / A / B


sniper_settings = SniperSettings()
