# binance/binance_stream.py
# Stream kline 5m dari Binance futures & jalankan analisa sniper.

import asyncio
import json
from typing import Dict, List

import websockets

from binance.binance_pairs import get_usdt_pairs
from sniper.sniper_analyzer import analyze_symbol_sniper
from binance.ohlc_buffer import Candle
from telegram import telegram_broadcast as tb
from core.bot_state import state

BINANCE_WS_URL = "wss://fstream.binance.com/stream"

# buffer candle sederhana per symbol
_candles_5m: Dict[str, List[Candle]] = {}


def _parse_kline_to_candle(k: dict) -> Candle:
    return {
        "open": float(k["o"]),
        "high": float(k["h"]),
        "low": float(k["l"]),
        "close": float(k["c"]),
        "volume": float(k["v"]),
        "open_time": int(k["t"]),
        "close_time": int(k["T"]),
    }


def _send_signal_telegram(result: Dict):
    text = result.get("message", "")

    if hasattr(tb, "broadcast_signal"):
        tb.broadcast_signal(result)
    elif hasattr(tb, "broadcast_imb_signal"):
        tb.broadcast_imb_signal(result)
    elif hasattr(tb, "send_signal_to_admins"):
        tb.send_signal_to_admins(text)
    else:
        print(text)


async def _handle_kline_stream():
    # pakai setting dinamis dari state (bisa diubah via Telegram)
    symbols = get_usdt_pairs(
        max_pairs=state.max_pairs,
        min_volume_usdt=state.min_volume_usdt,
    )

    if not symbols:
        print("Tidak ada pair yang lolos filter volume.")
        await asyncio.sleep(10)
        return

    print(f"Sniper scanning {len(symbols)} pair "
          f"(min_volume_usdt={state.min_volume_usdt:,.0f})")

    stream_names = [f"{s}@kline_5m" for s in symbols]
    url = f"{BINANCE_WS_URL}?streams={'/'.join(stream_names)}"

    async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
        print("Sniper stream connected!")

        while True:
            try:
                msg = await ws.recv()
            except websockets.ConnectionClosed:
                print("WS Closed — reconnecting...")
                break

            data = json.loads(msg)
            if "data" not in data:
                continue

            stream = data.get("stream", "")
            kline = data["data"].get("k")
            if not kline:
                continue

            # hanya proses candle yang sudah close
            if not kline.get("x", False):
                continue

            symbol = stream.split("@")[0].upper()
            candle = _parse_kline_to_candle(kline)

            buf = _candles_5m.setdefault(symbol, [])
            buf.append(candle)
            if len(buf) > 300:
                del buf[0: len(buf) - 300]

            result = analyze_symbol_sniper(symbol, buf)
            if result:
                _send_signal_telegram(result)


async def run_sniper_bot():
    """Loop reconnect utama sniper bot."""
    while True:
        try:
            await _handle_kline_stream()
        except Exception as e:
            print("Stream error:", e)

        await asyncio.sleep(3)
