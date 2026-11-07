from telegram import Bot
import logging

logger = logging.getLogger(__name__)

class TelegramPublisher:
    def __init__(self, token: str):
        self.bot = Bot(token=token)

    async def publish(self, chat_id: str, text: str):
        try:
            await self.bot.send_message(chat_id=chat_id, text=text)
            logger.info(f"Message published to {chat_id}")
        except Exception as e:
            logger.error(f"Publish failed: {e}")
            raise
