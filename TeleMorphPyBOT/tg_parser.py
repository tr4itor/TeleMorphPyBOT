import httpx
from bs4 import BeautifulSoup
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class TelegramParser:
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPStatusError)
    )
    async def fetch_channel_posts(self, channel: str):
        url = f"https://t.me/s/{channel}"
        response = await self.client.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        messages = soup.find_all('div', class_='tgme_widget_message')
        posts = []
        for msg in messages:
            post_id = msg.get('data-post')
            text_div = msg.find('div', class_='tgme_widget_message_text')
            text = text_div.get_text(strip=False) if text_div else ''
            if post_id:
                posts.append({
                    'id': post_id,
                    'text': text
                })
        
        posts.reverse()
        logger.debug(f"Fetched {len(posts)} posts from {channel}, newest: {posts[0]['id'] if posts else None}")
        return posts

    async def close(self):
        await self.client.aclose()
