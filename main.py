# main.py
# Entry point bot Sniper Reversal

import asyncio

from binance.binance_stream import run_sniper_stream
from telegram.telegram_core import run_telegram_bot
from core.bot_state import state
from sniper.sniper_settings import sniper_settings


async def main():
    print("🚀 SNIPER REVERSAL BOT started")

    # set default minimal tier untuk sinyal
    if not state.min_tier:
        state.min_tier = sniper_settings.default_min_tier

    await asyncio.gather(
        run_telegram_bot(),   # reuse dari project lama
        run_sniper_stream(),  # stream Binance khusus sniper
    )


if __name__ == "__main__":
    asyncio.run(main())
