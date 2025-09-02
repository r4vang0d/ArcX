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
from core.bot.telegram_bot import TelegramBotCore
from inline_handler import InlineHandler

# Import all feature handlers
from features.channel_management.handler import ChannelManagementHandler
from features.view_manager.handler import ViewManagerHandler
from features.emoji_reactions.handler import EmojiReactionsHandler
from features.analytics.handler import AnalyticsHandler
from features.account_management.handler import AccountManagementHandler
from features.system_health.handler import SystemHealthHandler
from features.live_management.handler import LiveManagementHandler
from features.poll_manager.handler import PollManagerHandler

logger = logging.getLogger(__name__)


class TelegramBot:
    """Main Telegram Bot Controller"""
    
    def __init__(self, config: Config, db_manager: DatabaseManager):
        self.config = config
        self.db_manager = db_manager
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self.handlers: Dict[str, Any] = {}
        self.bot_core: Optional[TelegramBotCore] = None
        
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
            
            # Initialize bot core for Telethon clients
            self.bot_core = TelegramBotCore(self.config, self.db_manager)
            # Mark as shared instance using setattr to avoid type checker issues
            setattr(self.bot_core, '_shared', True)
            await self.bot_core.initialize()
            
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
        """Initialize all feature handlers in parallel for faster startup"""
        try:
            # Ensure bot instance is available
            if self.bot is None:
                raise RuntimeError("Bot instance not initialized")
                
            # Create all handler instances first (fast) - pass bot_core to handlers that need it
            self.handlers['channel_management'] = ChannelManagementHandler(
                self.bot, self.db_manager, self.config, self.bot_core
            )
            self.handlers['view_manager'] = ViewManagerHandler(
                self.bot, self.db_manager, self.config, self.bot_core
            )
            self.handlers['emoji_reactions'] = EmojiReactionsHandler(
                self.bot, self.db_manager, self.config, self.bot_core
            )
            self.handlers['analytics'] = AnalyticsHandler(
                self.bot, self.db_manager, self.config
            )
            self.handlers['account_management'] = AccountManagementHandler(
                self.bot, self.db_manager, self.config, self.bot_core
            )
            self.handlers['system_health'] = SystemHealthHandler(
                self.bot, self.db_manager, self.config
            )
            self.handlers['live_management'] = LiveManagementHandler(
                self.bot, self.db_manager, self.config, self.bot_core
            )
            self.handlers['poll_manager'] = PollManagerHandler(
                self.bot, self.db_manager, self.config, self.bot_core
            )
            
            # Initialize all handlers in parallel (much faster)
            initialization_tasks = []
            for handler_name, handler in self.handlers.items():
                if hasattr(handler, 'initialize'):
                    initialization_tasks.append(self._initialize_single_handler(handler_name, handler))
            
            # Wait for all initializations to complete simultaneously
            if initialization_tasks:
                await asyncio.gather(*initialization_tasks)
                
        except Exception as e:
            logger.error(f"Failed to initialize handlers: {e}")
            raise
    
    async def _initialize_single_handler(self, handler_name: str, handler):
        """Initialize a single handler with logging"""
        try:
            await handler.initialize()
            logger.info(f"✅ {handler_name} handler initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize {handler_name}: {e}")
            raise
    
    def _register_routes(self):
        """Register all bot routes and handlers"""
        try:
            # Ensure dispatcher is available
            if self.dp is None:
                raise RuntimeError("Dispatcher not initialized")
                
            # Register start command
            self.dp.message.register(self._start_command, CommandStart())
            self.dp.message.register(self._help_command, Command("help"))
            
            # Register feature handlers with dispatcher (for non-callback handlers like message handlers)
            for handler_name, handler in self.handlers.items():
                if hasattr(handler, 'register_handlers'):
                    handler.register_handlers(self.dp)
                    logger.info(f"✅ {handler_name} routes registered")
            
            # Register inline callback handler AFTER feature handlers to avoid conflicts
            self.dp.callback_query.register(
                self.inline_handler.handle_callback,
                lambda c: True
            )
            
            # Register callback prefixes with inline handler for proper routing
            self.inline_handler.register_handler("account_manager", self.handlers['account_management'])
            self.inline_handler.register_handler("channel_manager", self.handlers['channel_management'])
            self.inline_handler.register_handler("views_manager", self.handlers['view_manager']) 
            self.inline_handler.register_handler("poll_manager", self.handlers['poll_manager'])
            self.inline_handler.register_handler("live_manager", self.handlers['live_management'])
            self.inline_handler.register_handler("analytics", self.handlers['analytics'])
            self.inline_handler.register_handler("emoji_reaction", self.handlers['emoji_reactions'])
            
            logger.info("✅ All routes registered successfully")
            
        except Exception as e:
            logger.error(f"Failed to register routes: {e}")
            raise
    
    async def _start_command(self, message: Message):
        """Handle /start command"""
        try:
            if message.from_user is None:
                logger.warning("Received message without user information")
                return
                
            user_id = message.from_user.id
            username = message.from_user.username or "Unknown"
            
            # Log user interaction
            logger.info(f"👤 USER INTERACTION: User {user_id} (@{username}) sent /start command")
            
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
            
            logger.info(f"🤖 BOT RESPONSE: Sending welcome message to user {user_id}")
            await message.answer(welcome_text, reply_markup=keyboard)
            
        except Exception as e:
            logger.error(f"Error in start command: {e}")
            await message.answer("❌ An error occurred. Please try again later.")
    
    async def _help_command(self, message: Message):
        """Handle /help command"""
        if message.from_user is None:
            logger.warning("Received help command without user information")
            return
            
        user_id = message.from_user.id
        username = message.from_user.username or "Unknown"
        
        logger.info(f"👤 USER INTERACTION: User {user_id} (@{username}) sent /help command")
        
        help_text = """
🔥 <b>ArcX Bot - Help Documentation</b>

<b>📋 Feature Guide:</b>

📱 <b>[Account Manager]</b>
• Add accounts with default/custom API
• Remove accounts and session cleanup
• List accounts with detailed info
• Refresh account status

📺 <b>[Channel Manager]</b> 
• Universal link handler for any channel type
• Add/remove channels from all accounts
• View channel statistics and member count
• Generate unique channel IDs for operations

🚀 <b>[Views Manager]</b>
• Auto Boost: Configure timing, cooldown, view counts
• Manual Boost: Instant view boosting
• Advanced scheduling with custom time formats
• Per-channel configuration settings

🗳️ <b>[Poll Manager]</b>
• Universal poll link handler
• Vote with multiple accounts
• Select voting options and distribution
• Real-time voting progress tracking

🎙️ <b>[Live Manager]</b>
• Auto-join live streams and voice chats
• WebRTC audio streaming (silent audio)
• Random hand raising and interactions
• Configurable participation settings

📊 <b>[Analytics]</b>
• Per-channel performance metrics
• System health and resource monitoring
• Engine status tracking
• Database connection statistics

😀 <b>[Emoji Reaction]</b>
• React to latest messages automatically
• Random emoji distribution strategies
• Custom reaction counts per message
• Multi-account reaction coordination

<b>👨‍💻 Developer:</b> @damn_itd_ravan
        """
        
        logger.info(f"🤖 BOT RESPONSE: Sending help message to user {user_id}")
        await message.answer(help_text)
    
    def _get_welcome_message(self, is_admin: bool, username: str) -> str:
        """Generate welcome message based on user type"""
        if is_admin:
            return f"""
🔥 <b>Welcome to ArcX Bot, {username}!</b>

🚀 <b>Advanced Telegram Channel Management System</b>

✨ You have full access to all premium features. 
If you need help with any feature, use /help for detailed documentation.

Select a feature below:
            """
        else:
            return f"""
🚫 <b>Access Restricted</b>

Hi {username}! This is a premium Telegram channel management bot.

🤖 <b>ArcX Bot</b> - Advanced Channel Management
• Multi-account automation
• View boosting systems  
• Live stream management
• Advanced analytics

This bot is for authorized users only.

👨‍💻 Developer: @damn_itd_ravan
            """
    
    def _get_main_keyboard(self, is_admin: bool) -> InlineKeyboardMarkup:
        """Generate main menu keyboard based on user type"""
        if not is_admin:
            # Non-admin gets restricted access - only show contact info
            return InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👨‍💻 Contact Developer", url="https://t.me/damn_itd_ravan")]
            ])
        
        # Admin gets full access with ArcX branded layout
        buttons = []
        
        # First row - Account & Channel management
        buttons.append([
            InlineKeyboardButton(text="[📱 Account Manager]", callback_data="account_manager"),
            InlineKeyboardButton(text="[📺 Channel Manager]", callback_data="channel_manager")
        ])
        
        # Second row - Views & Poll management  
        buttons.append([
            InlineKeyboardButton(text="[🚀 Views Manager]", callback_data="views_manager"),
            InlineKeyboardButton(text="[🗳️ Poll Manager]", callback_data="poll_manager")
        ])
        
        # Third row - Live & Analytics
        buttons.append([
            InlineKeyboardButton(text="[🎙️ Live Manager]", callback_data="live_manager"),
            InlineKeyboardButton(text="[📊 Analytics]", callback_data="analytics")
        ])
        
        # Fourth row - Emoji reactions (full width)
        buttons.append([
            InlineKeyboardButton(text="[😀 Emoji Reaction]", callback_data="emoji_reaction")
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    async def start(self):
        """Start the bot"""
        try:
            if self.dp is None or self.bot is None:
                raise RuntimeError("Bot or dispatcher not initialized")
                
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
            
            # Shutdown bot core (Telethon clients)
            if self.bot_core:
                await self.bot_core.shutdown()
            
            # Close bot session
            if self.bot:
                await self.bot.session.close()
            
            logger.info("✅ Bot shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
