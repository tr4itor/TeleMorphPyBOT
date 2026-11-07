import logging
import asyncio
import secrets
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackContext, CommandHandler, CallbackQueryHandler, MessageHandler, filters as telegram_filters
)
from config_manager import ConfigManager
import filters
from history_manager import HistoryManager

logger = logging.getLogger(__name__)

class AdminUI:
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.config = ConfigManager()
        self.history = HistoryManager()
        self.TOKEN_LIFETIME = 300

        self.setting_labels = {
            "parse_interval": "Parsing interval",
            "gemini_model": "Gemini model",
            "max_tokens": "Max. tokens",
            "temperature": "Temperature(0-1)",
            "gemini_api_key": "API-key Gemini"
        }

    async def _check_admin(self, update: Update) -> bool:
        user_id = update.effective_user.id
        admins = self.config.get_admins()
        return user_id in admins

    def _generate_token(self, context: CallbackContext, action: str, params: dict = None) -> str:
        token = secrets.token_urlsafe(16)
        context.user_data.setdefault('tokens', {})[token] = {
            'action': action,
            'params': params or {},
            'created_at': time.time()
        }
        return token

    def _validate_token(self, context: CallbackContext, token: str) -> tuple:
        tokens = context.user_data.get('tokens', {})
        if token not in tokens:
            return None, None
        data = tokens[token]
        if time.time() - data['created_at'] > self.TOKEN_LIFETIME:
            del tokens[token]
            return None, None
        del tokens[token]
        return data['action'], data['params']

    async def start(self, update: Update, context: CallbackContext):
        if not await self._check_admin(update):
            return
        context.user_data['expecting'] = None
        context.user_data['current_menu'] = 'main'
        context.user_data['tokens'] = {}
        keyboard = [
            [self._make_button("📋 Channels", "menu_channels", context=context)],
            [self._make_button("🎯 Target channel", "menu_target", context=context)],
            [self._make_button("📝 Prompt", "menu_prompt", context=context)],
            [self._make_button("🛑 Stopwords", "menu_stopwords", context=context)],
            [self._make_button("⚙️ Settings", "menu_settings", context=context)],
            [self._make_button("📊 Status", "menu_status", context=context)],
            [self._make_button("📜 History", "menu_history", context=context)],
            [self._make_button("🛑 Stop bot", "menu_stop", context=context)],
        ]
        await update.message.reply_text(
            "Main bot control menu\nSelect an action:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def handle_callback(self, update: Update, context: CallbackContext):
        query = update.callback_query
        if not await self._check_admin(update):
            await query.answer()
            return

        await query.answer()
        token = query.data
        action, params = self._validate_token(context, token)
        if action is None:
            await query.edit_message_text("❌ This action is outdated or invalid. Please reopen the menu via /start.")
            return

        current_menu = context.user_data.get('current_menu', 'main')

        if context.user_data.get('expecting'):
            if action == "cancel_input":
                context.user_data['expecting'] = None
                prev_menu = context.user_data.get('previous_menu', 'main')
                if prev_menu == 'channels':
                    await self._show_channels(query, context)
                elif prev_menu == 'target':
                    await self._show_target(query, context)
                elif prev_menu == 'prompt':
                    await self._show_prompt(query, context)
                elif prev_menu == 'stopwords':
                    await self._show_stopwords(query, context)
                elif prev_menu == 'settings':
                    await self._show_settings(query, context)
                elif prev_menu == 'history':
                    await self._show_history(query, context)
                else:
                    await self._go_to_main(query, context)
                return
            elif action == "menu_back":
                context.user_data['expecting'] = None
                await self._go_to_main(query, context)
                return
            await query.edit_message_text(
                "First, complete the editing (enter a value or click 'Cancel' or 'Back')."
            )
            return

        allowed_actions = {
            'main': ['menu_channels', 'menu_target', 'menu_prompt', 'menu_stopwords',
                     'menu_settings', 'menu_status', 'menu_history', 'menu_stop'],
            'channels': ['channels_add', 'channels_remove', 'menu_back', 'menu_channels'],
            'target': ['target_edit', 'menu_back', 'menu_target'],
            'prompt': ['prompt_edit', 'prompt_full', 'menu_back', 'menu_prompt'],
            'stopwords': ['stopwords_add', 'stopwords_remove', 'menu_back', 'menu_stopwords'],
            'settings': ['settings_edit', 'menu_back', 'menu_settings'],
            'status': ['menu_status', 'menu_back', 'pause_cycle', 'resume_cycle'],
            'history': ['menu_back', 'menu_history', 'history_clear'],
        }
        if action not in allowed_actions.get(current_menu, []):
            await query.edit_message_text("❌ This action is prohibited in the current menu.")
            return

        if action == "menu_channels":
            await self._show_channels(query, context)
        elif action == "menu_target":
            await self._show_target(query, context)
        elif action == "menu_prompt":
            await self._show_prompt(query, context)
        elif action == "menu_stopwords":
            await self._show_stopwords(query, context)
        elif action == "menu_settings":
            await self._show_settings(query, context)
        elif action == "menu_status":
            await self._show_status(query, context)
        elif action == "menu_history":
            await self._show_history(query, context)
        elif action == "menu_stop":
            await self._stop_bot(query, context)
        elif action == "menu_back":
            await self._go_to_main(query, context)
        elif action == "channels_add":
            await self._prompt_channel_add(query, context)
        elif action == "channels_remove":
            await self._remove_channel(query, params.get('channel'), context)
        elif action == "stopwords_add":
            await self._prompt_stopword_add(query, context)
        elif action == "stopwords_remove":
            await self._remove_stopword(query, params.get('idx'), context)
        elif action == "target_edit":
            await self._prompt_target_edit(query, context)
        elif action == "prompt_edit":
            await self._prompt_edit(query, context)
        elif action == "prompt_full":
            await self._show_prompt_full(query, context)
        elif action == "settings_edit":
            await self._prompt_setting_edit(query, params.get('param'), context)
        elif action == "pause_cycle":
            await self._pause_cycle(query, context)
        elif action == "resume_cycle":
            await self._resume_cycle(query, context)
        elif action == "history_clear":
            await self._clear_history(query, context)
        else:
            await query.edit_message_text("❌ Unknown action.")

    # ---------- AUXILIARY METHODS ----------
    def _make_button(self, text: str, action: str, params: dict = None, context: CallbackContext = None) -> InlineKeyboardButton:
        token = self._generate_token(context, action, params)
        return InlineKeyboardButton(text, callback_data=token)

    async def _go_to_main(self, query, context):
        context.user_data['current_menu'] = 'main'
        context.user_data['expecting'] = None
        context.user_data['tokens'] = {}
        keyboard = [
            [self._make_button("📋 Channels", "menu_channels", context=context)],
            [self._make_button("🎯 Target channel", "menu_target", context=context)],
            [self._make_button("📝 Prompt", "menu_prompt", context=context)],
            [self._make_button("🛑 Stopwords", "menu_stopwords", context=context)],
            [self._make_button("⚙️ Settings", "menu_settings", context=context)],
            [self._make_button("📊 Status", "menu_status", context=context)],
            [self._make_button("📜 History", "menu_history", context=context)],
            [self._make_button("🛑 Stop bot", "menu_stop", context=context)],
        ]
        await query.edit_message_text(
            "Main bot control menu\nSelect an action:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ---------- CHANNELS MENU ----------
    async def _show_channels(self, query, context):
        context.user_data['current_menu'] = 'channels'
        channels = self.config.get_channels()
        text = "Current channels for parsing:\n" + "\n".join(f"- {ch}" for ch in channels) if channels else "The list is empty."
        keyboard = []
        for ch in channels:
            keyboard.append([self._make_button(f"❌ {ch}", "channels_remove", {"channel": ch}, context)])
        keyboard.append([self._make_button("➕ Add channel", "channels_add", context=context)])
        keyboard.append([self._make_button("🔙 Back", "menu_back", context=context)])
        await query.edit_message_text(
            text + "\n\nActions:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _prompt_channel_add(self, query, context):
        context.user_data['previous_menu'] = context.user_data.get('current_menu', 'channels')
        await query.edit_message_text(
            "Enter the name of the channel to add (for example, durov):\n"
            "To cancel, click 'Cancel' (returns to the channel menu), 'Back' - to the main menu.
        )
        context.user_data['expecting'] = 'channel_add'
        keyboard = [
            [self._make_button("❌ Cancel", "cancel_input", context=context)],
            [self._make_button("🔙 Back", "menu_back", context=context)]
        ]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))

    async def _remove_channel(self, query, channel, context):
        if not channel:
            await query.edit_message_text("❌ Error: Channel not specified.")
            return
        channels = self.config.get_channels()
        if channel in channels:
            channels.remove(channel)
            self.config.save_channels(channels)
            self.bot.channels = channels
            await query.edit_message_text(f"✅ Channel {channel} deleted.")
        else:
            await query.edit_message_text(f"❌ Channel {channel} not found.")
        context.user_data['current_menu'] = 'channels'
        await self._show_channels(query, context)

    # ---------- TARGET CHANNEL MENU ----------
    async def _show_target(self, query, context):
        context.user_data['current_menu'] = 'target'
        target = self.config.get_target_channel()
        keyboard = [
            [self._make_button("✏️ Change", "target_edit", context=context)],
            [self._make_button("🔙 Back", "menu_back", context=context)],
        ]
        await query.edit_message_text(
            f"Current target channel: {target}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _prompt_target_edit(self, query, context):
        context.user_data['previous_menu'] = context.user_data.get('current_menu', 'target')
        await query.edit_message_text(
            "Enter the new ID or @name(without @) of the target channel:\n"
            "To cancel, click 'Cancel' (returns to the target channel menu), 'Back' - to the main menu."
        )
        context.user_data['expecting'] = 'target_edit'
        keyboard = [
            [self._make_button("❌ Cancel", "cancel_input", context=context)],
            [self._make_button("🔙 Back", "menu_back", context=context)]
        ]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))

    # ---------- PROMPT MENU ----------
    async def _show_prompt(self, query, context):
        context.user_data['current_menu'] = 'prompt'
        prompt = self.config.get_prompt()
        preview = prompt[:200] + "..." if len(prompt) > 200 else prompt
        keyboard = [
            [self._make_button("✏️ Edit", "prompt_edit", context=context)],
            [self._make_button("📋 Show in full", "prompt_full", context=context)],
            [self._make_button("🔙 Back", "menu_back", context=context)],
        ]
        await query.edit_message_text(
            f"Current prompt (first 200 characters):\n\n{preview}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _show_prompt_full(self, query, context):
        prompt = self.config.get_prompt()
        keyboard = [[self._make_button("🔙 Back", "menu_back", context=context)]]
        await query.edit_message_text(
            f"Full prompt:\n\n{prompt}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _prompt_edit(self, query, context):
        context.user_data['previous_menu'] = context.user_data.get('current_menu', 'prompt')
        await query.edit_message_text(
            "Send new prompt text (multi-line possible):\n"
            "To cancel, click 'Cancel' (returns to the target channel menu), 'Back' - to the main menu."
        )
        context.user_data['expecting'] = 'prompt_edit'
        keyboard = [
            [self._make_button("❌ Cancel", "cancel_input", context=context)],
            [self._make_button("🔙 Back", "menu_back", context=context)]
        ]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))

    # ---------- STOP WORD MENU ----------
    async def _show_stopwords(self, query, context):
        context.user_data['current_menu'] = 'stopwords'
        words = self.config.get_stopwords()
        text = "Stop words for the filter:\n" + "\n".join(f"- {w}" for w in words) if words else "The list is empty."
        keyboard = []
        for idx, word in enumerate(words):
            keyboard.append([self._make_button(f"❌ {word}", "stopwords_remove", {"idx": idx}, context)])
        keyboard.append([self._make_button("➕ Add a word", "stopwords_add", context=context)])
        keyboard.append([self._make_button("🔙 Back", "menu_back", context=context)])
        await query.edit_message_text(
            text + "\n\nActions:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _prompt_stopword_add(self, query, context):
        context.user_data['previous_menu'] = context.user_data.get('current_menu', 'stopwords')
        await query.edit_message_text(
            "Enter a word to add to the stop list:\n"
            "To cancel, click 'Cancel' (returns to the stopword menu), 'Back' - to the main menu."
        )
        context.user_data['expecting'] = 'stopword_add'
        keyboard = [
            [self._make_button("❌ Cancel", "cancel_input", context=context)],
            [self._make_button("🔙 Back", "menu_back", context=context)]
        ]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))

    async def _remove_stopword(self, query, idx, context):
        if idx is None:
            await query.edit_message_text("❌ Error: index not specified.")
            return
        words = self.config.get_stopwords()
        if 0 <= idx < len(words):
            removed = words.pop(idx)
            self.config.save_stopwords(words)
            filters.clear_cache()
            await query.edit_message_text(f"✅ Word {removed} deleted.")
        else:
            await query.edit_message_text("❌ Word not found.")
        context.user_data['current_menu'] = 'stopwords'
        await self._show_stopwords(query, context)

    # ---------- SETTINGS MENU----------
    async def _show_settings(self, query, context):
        context.user_data['current_menu'] = 'settings'
        settings = self.config.get_settings()
        text = "Settings:\n"
        keyboard = []
        for key, value in settings.items():
            # Skip log_level – do not display in the interface
            if key == 'log_level':
                continue
            label = self.setting_labels.get(key, key)
            # Hiding the value for the API key
            if key == 'gemini_api_key':
                display_value = "*****" if value else "(not installed)"
            else:
                display_value = value
            text += f"- {label}: {display_value}\n"
            keyboard.append([self._make_button(f"✏️ {label}", "settings_edit", {"param": key}, context)])
        keyboard.append([self._make_button("🔙 Back", "menu_back", context=context)])
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _prompt_setting_edit(self, query, param, context):
        if not param:
            await query.edit_message_text("❌ Error: parameter not specified.")
            return
        label = self.setting_labels.get(param, param)
        context.user_data['editing_setting'] = param
        context.user_data['previous_menu'] = context.user_data.get('current_menu', 'settings')
        await query.edit_message_text(
            f"Enter a new value for the parameter '{label}':\n"
            "To cancel, click 'Cancel' (returns to the settings menu), 'Back' - to the main menu."
        )
        context.user_data['expecting'] = f'edit_setting_{param}'
        keyboard = [
            [self._make_button("❌ Cancel", "cancel_input", context=context)],
            [self._make_button("🔙 Back", "menu_back", context=context)]
        ]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))

    # ---------- STATUS MENU ----------
    async def _show_status(self, query, context):
        context.user_data['current_menu'] = 'status'
        channels = self.config.get_channels()
        total = len(channels)
        interval = self.config.get_settings().get("parse_interval", 60)
        state = self.bot.state

        cycle = getattr(self.bot, 'cycle_counter', 0)
        is_scanning = getattr(self.bot, 'is_scanning', False)
        next_scan = getattr(self.bot, 'next_scan_time', None)
        pause = getattr(self.bot, 'pause_cycle', False)
        current_idx = getattr(self.bot, 'current_channel_index', 0)
        current_name = getattr(self.bot, 'current_channel_name', '')

        if pause:
            progress = "Suspended"
        elif is_scanning:
            if current_idx >= total:
                current_idx = total - 1
            progress = f"Channel processing {current_idx+1}/{total} ({current_name})"
        else:
            progress = f"Waiting (channels: {total})"

        if pause:
            time_to_scan = "Suspended"
        elif is_scanning:
            time_to_scan = "Scanning now"
        elif next_scan:
            delta = (next_scan - datetime.now()).total_seconds()
            if delta < 0:
                delta = 0
            time_to_scan = f"{int(delta)} с"
        else:
            time_to_scan = "Unknown"

        lines = [
            "📊 Bot status",
            f"🔄 Scan cycle: {cycle}",
            f"⏳ State: {'Scanning' if is_scanning else 'Rest' + (' (suspended)' if pause else '')}",
            f"⏱ Until the next scan: {time_to_scan}",
            f"📂 Progress: {progress}",
            f"⏱ Interval: {interval} с",
            "",
            "Latest IDs by channel:"
        ]
        for ch in channels:
            last_id = state.get(ch, "absent")
            lines.append(f"- {ch}: {last_id}")

        keyboard = []
        if not pause and self.bot._running:
            keyboard.append([self._make_button("⏸️ Pause the cycle", "pause_cycle", context=context)])
        elif pause and self.bot._running:
            keyboard.append([self._make_button("▶️ Resume the cycle", "resume_cycle", context=context)])
        keyboard.append([self._make_button("🔄 Update", "menu_status", context=context)])
        keyboard.append([self._make_button("🔙 Back", "menu_back", context=context)])

        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _pause_cycle(self, query, context):
        if not self.bot._running:
            await query.edit_message_text("❌ The bot is stopped, it is impossible to pause the cycle.")
            return
        await self.bot.pause_parsing()
        await query.edit_message_text("✅ The scan cycle is paused.")
        await self._show_status(query, context)

    async def _resume_cycle(self, query, context):
        if not self.bot._running:
            await query.edit_message_text("❌ The bot is stopped, it is impossible to resume the cycle.")
            return
        await self.bot.resume_parsing()
        await query.edit_message_text("✅ The scan cycle has resumed.")
        await self._show_status(query, context)

    # ---------- HISTORY MENU ----------
    async def _show_history(self, query, context):
        context.user_data['current_menu'] = 'history'
        records = self.history.get_recent(20)
        if not records:
            text = "📜 The publication history is empty."
            keyboard = [[self._make_button("🔙 Back", "menu_back", context=context)]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        lines = ["📜 Latest posts:"]
        for i, rec in enumerate(records, 1):
            timestamp = rec.get('timestamp', 'unknown')[:16]  # reduce to minutes
            channel = rec.get('channel', '')
            url = rec.get('original_url', '#')
            tokens = rec.get('tokens_used', 0)
            time_taken = rec.get('time_taken', 0)
            preview = rec.get('published_text', '')[:50] + "..." if len(rec.get('published_text', '')) > 50 else rec.get('published_text', '')
            lines.append(f"{i}. {timestamp} | {channel} | tokens: {tokens} | {time_taken:.1f}с")
            lines.append(f"   {preview}")
            lines.append(f"   🔗 {url}")

        text = "\n".join(lines)
        keyboard = [
            [self._make_button("🗑 Clear history", "history_clear", context=context)],
            [self._make_button("🔙 Back", "menu_back", context=context)]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    async def _clear_history(self, query, context):
        self.history.clear()
        await query.edit_message_text("✅ History cleared.")
        await self._show_history(query, context)

    # ---------- STOP ----------
    async def _stop_bot(self, query, context):
        await query.edit_message_text("🛑 Bot stops....")
        asyncio.create_task(self.bot.shutdown())

    # ---------- TEXT INPUT PROCESSOR  ----------
    async def handle_text_input(self, update: Update, context: CallbackContext):
        if not await self._check_admin(update):
            return

        expecting = context.user_data.get('expecting')
        if not expecting:
            await update.message.reply_text("❌ Nothing expected. Use /start for menu.")
            return

        # Editing settings
        if expecting.startswith('edit_setting_'):
            param = expecting.replace('edit_setting_', '')
            new_value_text = update.message.text.strip()
            settings = self.config.get_settings()
            old_value = settings.get(param)

            try:
                if isinstance(old_value, int):
                    new_value = int(new_value_text)
                elif isinstance(old_value, float):
                    new_value = float(new_value_text)
                elif isinstance(old_value, bool):
                    new_value = new_value_text.lower() in ('true', '1', 'yes', 'так')
                else:
                    new_value = new_value_text
            except ValueError:
                await update.message.reply_text(f"❌ Invalid format for parameter {param}. Expected {type(old_value).__name__}.")
                return

            settings[param] = new_value
            self.config.save_settings(settings)
            context.user_data['expecting'] = None
            context.user_data['current_menu'] = 'settings'
            await update.message.reply_text(f"✅ Parameter has been updated.")
            keyboard = [[self._make_button("Back to settings", "menu_settings", context=context)]]
            await update.message.reply_text("Settings updated.", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        # Adding a channel
        if expecting == 'channel_add':
            channel = update.message.text.strip()
            channels = self.config.get_channels()
            if channel not in channels:
                channels.append(channel)
                self.config.save_channels(channels)
                self.bot.channels = channels
                await update.message.reply_text(f"✅ Channel {channel} added.")
            else:
                await update.message.reply_text(f"❌ Channel {channel} already exists.")
            context.user_data['expecting'] = None
            context.user_data['current_menu'] = 'channels'
            return

        # Editing a target channel
        if expecting == 'target_edit':
            target = update.message.text.strip()
            self.config.save_target_channel(target)
            self.bot.target_channel = target
            await update.message.reply_text(f"✅ Target channel changed to{target}.")
            context.user_data['expecting'] = None
            context.user_data['current_menu'] = 'target'
            return

        # Editing a prompt
        if expecting == 'prompt_edit':
            new_prompt = update.message.text
            self.config.save_prompt(new_prompt)
            await update.message.reply_text("✅ Prompt has been updated.")
            context.user_data['expecting'] = None
            context.user_data['current_menu'] = 'prompt'
            return

        # Adding a stop word
        if expecting == 'stopword_add':
            word = update.message.text.strip()
            words = self.config.get_stopwords()
            if word not in words:
                words.append(word)
                self.config.save_stopwords(words)
                filters.clear_cache()
                await update.message.reply_text(f"✅ Word {word} added to the stop list.")
            else:
                await update.message.reply_text(f"❌ Word {word} is already on the list.")
            context.user_data['expecting'] = None
            context.user_data['current_menu'] = 'stopwords'
            return

        await update.message.reply_text("❌ Unknown action. Use /start for menu.")
        context.user_data['expecting'] = None

    # ---------- REGISTRATION ----------
    def register_handlers(self, app):
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CallbackQueryHandler(self.handle_callback))
        app.add_handler(MessageHandler(telegram_filters.TEXT & ~telegram_filters.COMMAND, self.handle_text_input))
