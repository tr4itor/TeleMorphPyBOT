import httpx
import logging
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep
from config_manager import ConfigManager

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self, config_manager: ConfigManager):
        self.config_mgr = config_manager
        self.client = httpx.AsyncClient(timeout=30.0)
        self.model = self.config_mgr.get_settings().get('gemini_model', 'gemini-3.1-flash-lite')
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        before_sleep=lambda retry_state: print(f"Gemini retry via {retry_state.next_action.sleep} seconds..")
    )
    async def rewrite_text(self, text: str) -> tuple:
        """
        Returns (transcribed_text, dictionary_usage)
        usage contains: prompt_tokens, completion_tokens, total_tokens
        """
        api_key = self.config_mgr.get_gemini_api_key()
        prompt_template = self.config_mgr.get_prompt()
        prompt = prompt_template.format(text[:4000])
        settings = self.config_mgr.get_settings()
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": settings.get('max_tokens', 4000),
                "temperature": settings.get('temperature', 0.7),
            }
        }
        url = f"{self.base_url}?key={api_key}"
        try:
            response = await self.client.post(url, json=payload)
        except httpx.ConnectError as e:
            logger.error(f"Connection error to Gemini: {e}")
            print(f"Gemini connection error: {e}")
            raise

        if response.status_code == 429:
            logger.warning("Gemini API rate limit exceeded (429)")
            print("Gemini limit exceeded (quota), waiting 60 seconds...")
            await asyncio.sleep(60)
            response.raise_for_status()
        elif response.status_code == 403:
            error_text = response.text
            logger.error(f"Gemini API forbidden (403): {error_text}")
            if "quota" in error_text.lower() or "limit" in error_text.lower():
                print("Gemini limit exceeded (quota), waiting 60 seconds...")
                await asyncio.sleep(60)
            else:
                print(f"Gemini error(403): {error_text[:100]}")
            response.raise_for_status()
        else:
            response.raise_for_status()

        data = response.json()
        try:
            text = data['candidates'][0]['content']['parts'][0]['text']
        except (KeyError, IndexError) as e:
            logger.error(f"Unexpected Gemini response: {data}")
            print(f"Gemini's unexpected response: {data}")
            return "", {}

        usage = data.get('usageMetadata', {})
        return text, usage

    async def close(self):
        await self.client.aclose()
