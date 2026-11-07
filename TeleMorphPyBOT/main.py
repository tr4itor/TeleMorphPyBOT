import asyncio
import json
import logging
import time
from pathlib import Path
from datetime import datetime, timedelta

import httpx
from telegram.ext import Application

from config_manager import ConfigManager
from admin_ui import AdminUI
from gemini import GeminiClient
from tg_parser import TelegramParser
from publisher import TelegramPublisher
from filters import remove_signatures
from history_manager import HistoryManager

BANNER = r"""
  _____    _      __  __                  _     
 |_   _|__| | ___|  \/  | ___  _ __ _ __ | |__  
   | |/ _ \ |/ _ \ |\/| |/ _ \| '__| '_ \| '_ \ 
   | |  __/ |  __/ |  | | (_) | |  | |_) | | | |
   |_|\___|_|\___|_|  |_|\___/|_|  | .__/|_| |_|
                                   |_|          
              
"""

# --- SETTING UP LOGS ---
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
start_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_file = log_dir / f"bot_{start_time}.log"

file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

config_mgr = ConfigManager()
log_level_str = config_mgr.get_settings().get('log_level', 'INFO')
log_level = getattr(logging, log_level_str.upper(), logging.INFO)

logging.basicConfig(
    level=log_level,
    handlers=[file_handler]
)
logger = logging.getLogger(__name__)


class Autobot:
    def __init__(self):
        self.config_mgr = ConfigManager()
        self._running = True
        self.history = HistoryManager()

        self.channels = self.config_mgr.get_channels()
        self.target_channel = self.config_mgr.get_target_channel()
        self.state = self._load_state()

        try:
            self.parser = TelegramParser()
            self.gemini = GeminiClient(self.config_mgr)
            self.publisher = TelegramPublisher(self.config_mgr.telegram_token)
        except ValueError as e:
            logger.critical(f"Missing token: {e}")
            raise

        self.app = Application.builder().token(self.config_mgr.telegram_token).build()
        self.admin_ui = AdminUI(self)
        self.admin_ui.register_handlers(self.app)

        self.polling_task = None
        self.cycle_task = None

        # Attributes for status
        self.cycle_counter = 0
        self.is_scanning = False
        self.next_scan_time = None
        self.pause_cycle = False
        self.current_channel_index = 0
        self.current_channel_name = ""

        logger.info("Autobot initialized")
        logger.info(f"Loaded channels: {self.channels}")
        logger.info(f"Target channel: {self.target_channel}")
        logger.info(f"State: {self.state}")

    # ---------- STATE ----------
    def _load_state(self) -> dict:
        state_file = Path("state.json")
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
                return {}
        return {}

    def _save_state(self):
        state_file = Path("state.json")
        try:
            with open(state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    # ---------- CHANNEL PROCESSING ----------
    async def process_channel(self, channel: str, index: int):
        self.current_channel_index = index
        self.current_channel_name = channel
        logger.info(f"Processing channel: {channel} ({index+1}/{len(self.channels)})")
        print(f"Channel scan: {channel} ...")

        try:
            posts = await self.parser.fetch_channel_posts(channel)
            if not posts:
                logger.info(f"No posts found for {channel}")
                print(f"Channel scan {channel} completed: 0 posts")
                return

            newest_post_id = posts[0]['id']
            logger.debug(f"Newest post ID for {channel}: {newest_post_id}")

            last_processed_id = self.state.get(channel)
            if last_processed_id is None:
                self.state[channel] = newest_post_id
                self._save_state()
                logger.info(f"First run for {channel}. Stored latest ID {newest_post_id}.")
                print(f"Channel scan {channel} completed: found {len(posts)} posts, new: 0 (first start)")
                return

            if last_processed_id == newest_post_id:
                logger.info(f"No new posts for {channel}")
                print(f"Channel scanу {channel} completed: found {len(posts)} posts, : 0")
                return

            try:
                last_idx = next(i for i, p in enumerate(posts) if p['id'] == last_processed_id)
            except StopIteration:
                self.state[channel] = newest_post_id
                self._save_state()
                logger.warning(f"Last processed ID {last_processed_id} not found. Stored latest.")
                print(f"Channel scan {channel} completed: found {len(posts)} posts, new: 0 (ID not found)")
                return

            new_posts = posts[:last_idx]
            if not new_posts:
                logger.info(f"No new posts for {channel}")
                print(f"Channel scan {channel} completed: found {len(posts)} posts, new: 0")
                return

            new_posts.reverse()
            logger.info(f"Found {len(new_posts)} new posts for {channel}")
            print(f"Channel scan {channel} completed: found {len(posts)} posts, new: {len(new_posts)}")

            for post in new_posts:
                if not self._running or self.pause_cycle:
                    break

                original = post['text']
                filtered = remove_signatures(original)
                if not filtered.strip():
                    logger.info(f"Post {post['id']} empty after filtering, skip")
                    print(f"Post {post['id']} skipped (empty after filtering)")
                    continue

                start_time = time.time()
                try:
                    rewritten, usage = await self.gemini.rewrite_text(filtered)
                except Exception as e:
                    logger.error(f"Gemini error for post {post['id']}: {e}")
                    print(f"Post {post['id']} skipped (Gemini error: {str(e)[:50]})")
                    continue

                if not rewritten:
                    logger.error(f"Gemini returned empty for post {post['id']}, skip")
                    print(f"Post {post['id']} skipped (empty answer Gemini)")
                    continue

                # Adding a link to the original
                post_id_part = post['id'].split('/')[-1]  # if format "channel/123"
                original_url = f"https://t.me/{channel}/{post_id_part}"
                full_text = f"{rewritten}\n\nOriginal: {original_url}"

                try:
                    await self.publisher.publish(self.target_channel, full_text)
                    print(f"Post published {post['id']} from {channel}")
                    self.state[channel] = post['id']
                    self._save_state()

                    # Saving to history
                    elapsed = time.time() - start_time
                    tokens_used = usage.get('total_tokens', 0)
                    self.history.add_record(
                        channel=channel,
                        original_post_id=post['id'],
                        original_url=original_url,
                        published_text=rewritten,
                        tokens_used=tokens_used,
                        time_taken=elapsed
                    )
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error(f"Publish failed for post {post['id']}: {e}")
                    print(f"Error publishing post {post['id']}")

            self.state[channel] = newest_post_id
            self._save_state()
            logger.info(f"Updated state for {channel} to latest ID: {newest_post_id}")

        except httpx.ConnectError as e:
            logger.error(f"Connection error for {channel}: {e}")
            print(f"Error connecting to channel {channel}, reconnect attempt...")
        except Exception as e:
            logger.error(f"Error processing {channel}: {e}", exc_info=True)
            print(f"Channel processing error {channel}: {str(e)[:100]}")

    # ---------- INFINITE CYCLE----------
    async def run_cycle(self):
        while self._running:
            try:
                while self.pause_cycle and self._running:
                    await asyncio.sleep(1)
                    continue
                if not self._running:
                    break

                self.cycle_counter += 1
                self.is_scanning = True
                self.next_scan_time = None
                logger.info(f"Starting parse cycle #{self.cycle_counter}")
                print(f"Scan cycle #{self.cycle_counter} started")

                self.channels = self.config_mgr.get_channels()
                self.target_channel = self.config_mgr.get_target_channel()
                interval = self.config_mgr.get_settings().get('parse_interval', 60)

                for idx, ch in enumerate(self.channels):
                    if not self._running or self.pause_cycle:
                        break
                    await self.process_channel(ch, idx)
                    await asyncio.sleep(5)

                self.is_scanning = False
                self.current_channel_name = ""
                if not self.pause_cycle:
                    self.next_scan_time = datetime.now() + timedelta(seconds=interval)

                logger.info(f"Cycle finished, sleeping {interval} seconds")
                print(f"Cycle complete, next scan through {interval} seconds")
                for _ in range(interval):
                    if not self._running or self.pause_cycle:
                        break
                    await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Cycle crashed: {e}", exc_info=True)
                print(f"Critical loop error: {str(e)[:100]}, restart in 60 seconds")
                await asyncio.sleep(60)

    # ---------- PAUSE CONTROL ----------
    async def pause_parsing(self):
        self.pause_cycle = True
        self.is_scanning = False
        self.next_scan_time = None
        logger.info("Cycle paused by admin")
        print("Scan cycle paused")

    async def resume_parsing(self):
        self.pause_cycle = False
        self.next_scan_time = None
        logger.info("Cycle resumed by admin")
        print("Scan cycle resumed")

    # ---------- STOP ----------
    async def shutdown(self):
        logger.info("Shutting down...")
        self._running = False

        if self.polling_task and not self.polling_task.done():
            try:
                await self.app.updater.stop_polling()
                await self.app.stop()
            except Exception as e:
                logger.error(f"Error stopping app: {e}")

        try:
            await self.parser.close()
        except Exception as e:
            logger.error(f"Error closing parser: {e}")
        try:
            await self.gemini.close()
        except Exception as e:
            logger.error(f"Error closing gemini: {e}")

        state_path = Path("state.json")
        if state_path.exists():
            try:
                state_path.unlink()
                logger.info("state.json deleted")
                print("state.json deleted")
            except Exception as e:
                logger.error(f"Failed to delete state.json: {e}")

        print("The bot has been completely stopped.")
        logger.info("Bot stopped")

    # ---------- START ----------
    async def run(self):
        print(BANNER)
        print("Bot started. Waiting for commands...")
        logger.info("Bot started")

        await self.app.initialize()
        await self.app.start()

        self.polling_task = asyncio.create_task(self.app.updater.start_polling())
        self.cycle_task = asyncio.create_task(self.run_cycle())

        try:
            await asyncio.gather(self.polling_task, self.cycle_task)
        except asyncio.CancelledError:
            logger.info("Tasks cancelled")
        finally:
            await self.shutdown()


async def main():
    bot = None
    try:
        bot = Autobot()
        await bot.run()
    except KeyboardInterrupt:
        print("Bot stopped by request")
        logger.info("Bot stopped by KeyboardInterrupt")
        if bot:
            await bot.shutdown()
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        print(f"Critical error: {e}")
        if bot:
            await bot.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by request (asyncio)")
