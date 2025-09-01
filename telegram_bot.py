"""
Telegram Bot Core Implementation
Main bot controller with feature routing and session management
"""

import asyncio
import logging
from typing import Dict, Any, Optional

from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from core.config.config import Config
from core.database.unified_database import DatabaseManager
from inline_handler import InlineHandler

# Import all feature handlers
from features.channel_management.handler import ChannelManagementHandler
from features.view_manager.handler import ViewManagerHandler
from features.emoji_reactions.handler import EmojiReactionsHandler
from features.analytics.handler import AnalyticsHandler
from features.account_management.handler import AccountManagementHandler
from features.system_health.handler import SystemHealthHandler
from features.live_management.handler import LiveManagementHandler

logger = logging.getLogger(__name__)


class TelegramBot:
    """Main Telegram Bot Controller"""
    
    def __init__(self, config: Config, db_manager: DatabaseManager):
        self.config = config
        self.db_manager = db_manager
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self.handlers: Dict[str, Any] = {}
        
    async def initialize(self):
        """Initialize bot and all handlers"""
        try:
            # Initialize bot instance
            self.bot = Bot(
                token=self.config.BOT_TOKEN,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML)
            )
            
            # Initialize dispatcher with memory storage
            storage = MemoryStorage()
            self.dp = Dispatcher(storage=storage)
            
            # Initialize inline handler
            self.inline_handler = InlineHandler(self.bot, self.db_manager, self.config)
            
            # Initialize feature handlers
            await self._initialize_handlers()
            
            # Register routes
            self._register_routes()
            
            logger.info("✅ Bot initialization completed")
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            raise
    
    async def _initialize_handlers(self):
        """Initialize all feature handlers"""
        try:
            # Initialize each handler with dependencies
            self.handlers['channel_management'] = ChannelManagementHandler(
                self.bot, self.db_manager, self.config
            )
            
            self.handlers['view_manager'] = ViewManagerHandler(
                self.bot, self.db_manager, self.config
            )
            
            self.handlers['emoji_reactions'] = EmojiReactionsHandler(
                self.bot, self.db_manager, self.config
            )
            
            self.handlers['analytics'] = AnalyticsHandler(
                self.bot, self.db_manager, self.config
            )
            
            self.handlers['account_management'] = AccountManagementHandler(
                self.bot, self.db_manager, self.config
            )
            
            self.handlers['system_health'] = SystemHealthHandler(
                self.bot, self.db_manager, self.config
            )
            
            self.handlers['live_management'] = LiveManagementHandler(
                self.bot, self.db_manager, self.config
            )
            
            
            # Initialize all handlers
            for handler_name, handler in self.handlers.items():
                if hasattr(handler, 'initialize'):
                    await handler.initialize()
                logger.info(f"✅ {handler_name} handler initialized")
                
        except Exception as e:
            logger.error(f"Failed to initialize handlers: {e}")
            raise
    
    def _register_routes(self):
        """Register all bot routes and handlers"""
        try:
            # Register start command
            self.dp.message.register(self._start_command, CommandStart())
            self.dp.message.register(self._help_command, Command("help"))
            
            # Register inline callback handler
            self.dp.callback_query.register(
                self.inline_handler.handle_callback,
                lambda c: True
            )
            
            # Register feature handlers with dispatcher
            for handler_name, handler in self.handlers.items():
                if hasattr(handler, 'register_handlers'):
                    handler.register_handlers(self.dp)
                    logger.info(f"✅ {handler_name} routes registered")
            
            logger.info("✅ All routes registered successfully")
            
        except Exception as e:
            logger.error(f"Failed to register routes: {e}")
            raise
    
    async def _start_command(self, message: Message):
        """Handle /start command"""
        try:
            user_id = message.from_user.id
            username = message.from_user.username or "Unknown"
            
            # Check if user is admin
            is_admin = user_id in self.config.ADMIN_IDS
            
            # Store user info in database
            await self.db_manager.execute_query(
                """
                INSERT INTO users (user_id, username, is_admin, first_seen, last_seen)
                VALUES ($1, $2, $3, NOW(), NOW())
                ON CONFLICT (user_id) 
                DO UPDATE SET username = $2, last_seen = NOW()
                """,
                user_id, username, is_admin
            )
            
            # Create welcome message
            welcome_text = self._get_welcome_message(is_admin, username)
            keyboard = self._get_main_keyboard(is_admin)
            
            await message.answer(welcome_text, reply_markup=keyboard)
            
        except Exception as e:
            logger.error(f"Error in start command: {e}")
            await message.answer("❌ An error occurred. Please try again later.")
    
    async def _help_command(self, message: Message):
        """Handle /help command"""
        help_text = """
🤖 <b>Telegram Channel Management Bot</b>

<b>📋 Available Features:</b>
🎯 <b>Channel Management</b> - Add and manage your channels
🚀 <b>View Boosting</b> - Boost views on posts automatically
🎭 <b>Emoji Reactions</b> - Add emoji reactions to posts
📊 <b>Analytics</b> - View detailed statistics
📱 <b>Account Management</b> - Manage multiple Telegram accounts
🎙️ <b>Live Management</b> - Join live streams automatically
👁️ <b>View Monitoring</b> - Monitor view counts in real-time
💚 <b>System Health</b> - Check bot performance

<b>💡 Getting Started:</b>
1. Use /start to see the main menu
2. Add your channels first
3. Configure your accounts
4. Start boosting views!

<b>🆘 Need Help?</b>
Contact the bot administrators for assistance.
        """
        
        await message.answer(help_text)
    
    def _get_welcome_message(self, is_admin: bool, username: str) -> str:
        """Generate welcome message based on user type"""
        if is_admin:
            return f"""
🎯 <b>Welcome Back, Admin {username}!</b>

You have full access to all bot features including:
• Channel Management & View Boosting
• Account Management & Live Streaming
• Analytics & System Health Monitoring
• Complete Bot Administration

Select an option below to get started:
            """
        else:
            return f"""
👋 <b>Welcome, {username}!</b>

🚀 <b>Telegram Channel Management Bot</b>

This bot helps you manage your Telegram channels and boost engagement through:
• Automated view boosting
• Emoji reactions management
• Live stream participation
• Real-time analytics

Select an option below to get started:
            """
    
    def _get_main_keyboard(self, is_admin: bool) -> InlineKeyboardMarkup:
        """Generate main menu keyboard based on user type"""
        buttons = []
        
        # Core features available to all users
        buttons.append([
            InlineKeyboardButton(text="🎯 Channel Management", callback_data="channel_management")
        ])
        buttons.append([
            InlineKeyboardButton(text="🚀 Boost Views", callback_data="view_manager"),
            InlineKeyboardButton(text="🎭 Emoji Reactions", callback_data="emoji_reactions")
        ])
        buttons.append([
            InlineKeyboardButton(text="📊 Analytics", callback_data="analytics")
        ])
        
        # Advanced features
        buttons.append([
            InlineKeyboardButton(text="📱 Manage Accounts", callback_data="account_management"),
            InlineKeyboardButton(text="🎙️ Live Management", callback_data="live_management")
        ])
        
        # Admin-only features
        if is_admin:
            buttons.append([
                InlineKeyboardButton(text="💚 System Health", callback_data="system_health")
            ])
        
        # Help and refresh
        buttons.append([
            InlineKeyboardButton(text="❓ Help", callback_data="help"),
            InlineKeyboardButton(text="🔄 Refresh", callback_data="refresh_main")
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    async def start(self):
        """Start the bot"""
        try:
            logger.info("🎯 Starting bot polling...")
            await self.dp.start_polling(self.bot)
        except Exception as e:
            logger.error(f"Error during polling: {e}")
            raise
    
    async def shutdown(self):
        """Shutdown the bot gracefully"""
        try:
            logger.info("⏹️ Shutting down bot...")
            
            # Close all handlers
            for handler_name, handler in self.handlers.items():
                if hasattr(handler, 'shutdown'):
                    await handler.shutdown()
            
            # Close bot session
            if self.bot:
                await self.bot.session.close()
            
            logger.info("✅ Bot shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
