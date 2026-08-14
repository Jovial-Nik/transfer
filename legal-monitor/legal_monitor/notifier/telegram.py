from __future__ import annotations

import asyncio
import logging

from telegram import Bot
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id

    def send(self, messages: list[str]) -> None:
        if not messages:
            return
        asyncio.run(self._send_async(messages))

    async def _send_async(self, messages: list[str]) -> None:
        bot = Bot(token=self._bot_token)
        for i, text in enumerate(messages):
            logger.info("sending Telegram message %d/%d (%d chars)", i + 1, len(messages), len(text))
            await bot.send_message(chat_id=self._chat_id, text=text, parse_mode=ParseMode.HTML)
