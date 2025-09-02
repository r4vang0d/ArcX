"""
Central Inline Button Router
Handles all inline keyboard callbacks and routes them to appropriate handlers
"""

import logging
from typing import Dict, Any, Optional

from aiogram import Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from core.config.config import Config
from core.database.unified_database import DatabaseManager

logger = logging.getLogger(__name__)


class InlineHandler:
    """Central router for all inline button callbacks"""
    
    def __init__(self, bot: Bot, db_manager: DatabaseManager, config: Config):
        self.bot = bot
        self.db_manager = db_manager
        self.config = config
        self.handlers: Dict[str, Any] = {}
        
    def register_handler(self, prefix: str, handler: Any):
        """Register a handler for a specific callback prefix"""
        self.handlers[prefix] = handler
        logger.info(f"✅ Registered inline handler for prefix: {prefix}")
    
    async def handle_callback(self, callback: CallbackQuery, state: FSMContext):
        """Route callback to appropriate handler based on prefix"""
        try:
            callback_data = callback.data
            user_id = callback.from_user.id
            username = callback.from_user.username or "Unknown"
            
            # Enhanced logging with user details
            logger.info(f"🔘 BUTTON PRESSED: User {user_id} (@{username}) clicked '{callback_data}'")
            
            # Handle main menu callbacks
            if callback_data in self._get_main_menu_callbacks():
                logger.info(f"🏠 MAIN MENU: Routing '{callback_data}' to main menu handler")
                await self._handle_main_menu_callback(callback)
                return
            
            # Route to specific handlers based on prefix
            # Account Management callbacks
            if callback_data.startswith("am_"):
                if "account_manager" in self.handlers:
                    logger.info(f"🔄 ROUTING: Account Manager callback '{callback_data}'")
                    await self.handlers["account_manager"].handle_callback(callback, state)
                    return
            
            # Channel Management callbacks
            if callback_data.startswith("cm_"):
                if "channel_manager" in self.handlers:
                    logger.info(f"🔄 ROUTING: Channel Manager callback '{callback_data}'")
                    await self.handlers["channel_manager"].handle_callback(callback, state)
                    return
            
            # View Manager callbacks
            if callback_data.startswith("vm_"):
                if "views_manager" in self.handlers:
                    logger.info(f"🔄 ROUTING: Views Manager callback '{callback_data}'")
                    await self.handlers["views_manager"].handle_callback(callback, state)
                    return
            
            # Live Management callbacks
            if callback_data.startswith("lm_") or callback_data.startswith("aj_") or callback_data.startswith("mj_") or callback_data.startswith("vs_") or callback_data.startswith("ls_"):
                if "live_manager" in self.handlers:
                    logger.info(f"🔄 ROUTING: Live Manager callback '{callback_data}'")
                    await self.handlers["live_manager"].handle_callback(callback, state)
                    return
            
            # Analytics callbacks
            if callback_data.startswith("an_"):
                if "analytics" in self.handlers:
                    logger.info(f"🔄 ROUTING: Analytics callback '{callback_data}'")
                    await self.handlers["analytics"].handle_callback(callback, state)
                    return
            
            # Emoji Reactions callbacks
            if callback_data.startswith("er_"):
                if "emoji_reaction" in self.handlers:
                    logger.info(f"🔄 ROUTING: Emoji Reactions callback '{callback_data}'")
                    await self.handlers["emoji_reaction"].handle_callback(callback, state)
                    return
            
            # System Health callbacks
            if callback_data.startswith("sh_"):
                if "system_health" in self.handlers:
                    logger.info(f"🔄 ROUTING: System Health callback '{callback_data}'")
                    await self.handlers["system_health"].handle_callback(callback, state)
                    return
            
            # Poll Manager callbacks (using emoji reactions handler temporarily)
            if callback_data.startswith("pm_"):
                if "emoji_reaction" in self.handlers:
                    logger.info(f"🔄 ROUTING: Poll Manager callback '{callback_data}' to emoji reactions")
                    await self.handlers["emoji_reaction"].handle_callback(callback, state)
                    return
            
            # Auto Boost specific callbacks
            if callback_data.startswith("ab_"):
                if "views_manager" in self.handlers:
                    logger.info(f"🔄 ROUTING: Auto Boost callback '{callback_data}'")
                    await self.handlers["views_manager"].handle_callback(callback, state)
                    return
            
            # Handle unknown callbacks
            logger.warning(f"❓ UNKNOWN CALLBACK: '{callback_data}' from user {user_id}")
            await self._handle_unknown_callback(callback)
            
        except Exception as e:
            logger.error(f"❌ CALLBACK ERROR: Error handling callback '{callback.data}' from user {callback.from_user.id}: {e}")
            try:
                # Check if it's a timeout error and handle gracefully
                if "query is too old" in str(e) or "timeout expired" in str(e):
                    logger.info("⏰ EXPIRED CALLBACK: Ignoring expired callback query")
                    return
                logger.info(f"🤖 ERROR RESPONSE: Sending error message to user {callback.from_user.id}")
                await callback.answer("❌ An error occurred. Please try again.", show_alert=True)
            except Exception as answer_error:
                # If we can't answer the callback (e.g., expired), just log it
                logger.info(f"⚠️ CALLBACK ANSWER FAILED: Could not answer callback (likely expired): {answer_error}")
    
    def _get_main_menu_callbacks(self) -> set:
        """Get set of main menu callback data"""
        return {
            "account_manager", "channel_manager", "views_manager", 
            "poll_manager", "live_manager", "analytics", 
            "emoji_reaction", "help", "refresh_main"
        }
    
    async def _handle_main_menu_callback(self, callback: CallbackQuery):
        """Handle main menu callbacks"""
        try:
            callback_data = callback.data
            user_id = callback.from_user.id
            username = callback.from_user.username or "User"
            
            logger.info(f"📋 MAIN MENU ACTION: User {user_id} (@{username}) selected '{callback_data}'")
            
            # Check admin status for restricted features
            is_admin = user_id in self.config.ADMIN_IDS
            
            if callback_data == "refresh_main":
                # Import the method from telegram_bot.py
                from telegram_bot import TelegramBot
                temp_bot = TelegramBot(self.config, self.db_manager)
                welcome_text = temp_bot._get_welcome_message(is_admin, username)
                keyboard = temp_bot._get_main_keyboard(is_admin)
                
                await callback.message.edit_text(welcome_text, reply_markup=keyboard)
                await callback.answer("🔄 Menu refreshed!")
                logger.info(f"🤖 RESPONSE: Main menu refreshed for user {user_id}")
                
            elif callback_data == "help":
                # Show help information
                logger.info(f"❓ HELP REQUEST: User {user_id} requested help menu")
                await self._show_help_menu(callback)
                
            else:
                # Route to feature handlers
                logger.info(f"🎯 FEATURE ACCESS: User {user_id} accessing '{callback_data}' feature")
                await self._route_to_feature(callback, callback_data)
                
        except Exception as e:
            logger.error(f"❌ MAIN MENU ERROR: Error in main menu callback for user {callback.from_user.id}: {e}")
            await callback.answer("❌ An error occurred.", show_alert=True)
    
    async def _route_to_feature(self, callback: CallbackQuery, feature: str):
        """Route callback to specific feature handler"""
        try:
            user_id = callback.from_user.id
            is_admin = user_id in self.config.ADMIN_IDS
            
            # Check admin access for restricted features
            if not is_admin:
                await callback.answer("🚫 Access restricted to authorized users only!", show_alert=True)
                return
                
            feature_name = feature.replace('_', ' ').title()
            
            logger.info(f"🎯 FEATURE ROUTING: Loading '{feature_name}' for user {user_id}")
            
            # Create feature menu text and keyboard
            menu_text, menu_keyboard = await self._get_feature_menu(feature)
            
            logger.info(f"🤖 FEATURE RESPONSE: Sending '{feature_name}' menu to user {user_id}")
            await callback.message.edit_text(menu_text, reply_markup=menu_keyboard)
            await callback.answer(f"📋 {feature_name} loaded")
            
        except Exception as e:
            logger.error(f"❌ FEATURE ERROR: Error routing to feature '{feature}' for user {callback.from_user.id}: {e}")
            await callback.answer("❌ Feature temporarily unavailable", show_alert=True)
    
    async def _get_feature_menu(self, feature: str) -> tuple[str, InlineKeyboardMarkup]:
        """Generate menu text and keyboard for specific feature"""
        menus = {
            "account_manager": (
                "🔥 <b>ArcX | Account Manager</b>\\n\\n"
                "Manage your Telegram accounts for operations:\\n\\n",
                InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="[➕ Add Account]", callback_data="am_add_account")],
                    [InlineKeyboardButton(text="[🗑️ Remove Account]", callback_data="am_remove_account")],
                    [InlineKeyboardButton(text="[📋 List Accounts]", callback_data="am_list_accounts")],
                    [InlineKeyboardButton(text="[🔄 Refresh Accounts]", callback_data="am_refresh")],
                    [InlineKeyboardButton(text="[🔙 Back]", callback_data="refresh_main")],
                    [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
                ])
            ),
            "channel_manager": (
                "🔥 <b>ArcX | Channel Manager</b>\\n\\n"
                "Universal channel management system:\\n\\n",
                InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="[➕ Add Channel]", callback_data="cm_add_channel")],
                    [InlineKeyboardButton(text="[🗑️ Remove Channel]", callback_data="cm_remove_channel")],
                    [InlineKeyboardButton(text="[📋 List Channels]", callback_data="cm_list_channels")],
                    [InlineKeyboardButton(text="[🔄 Refresh Channels]", callback_data="cm_refresh")],
                    [InlineKeyboardButton(text="[🔙 Back]", callback_data="refresh_main")],
                    [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
                ])
            ),
            "views_manager": (
                "🔥 <b>ArcX | Views Manager</b>\\n\\n"
                "Advanced view boosting system:\\n\\n",
                InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="[🤖 Auto Boost]", callback_data="vm_auto_boost")],
                    [InlineKeyboardButton(text="[👆 Manual Boost]", callback_data="vm_manual_boost")],
                    [InlineKeyboardButton(text="[🔙 Back]", callback_data="refresh_main")],
                    [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
                ])
            ),
            "poll_manager": (
                "🔥 <b>ArcX | Poll Manager</b>\\n\\n"
                "Automated poll voting system:\\n\\n",
                InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="[🗳️ Vote on Poll]", callback_data="pm_vote_poll")],
                    [InlineKeyboardButton(text="[📊 Poll Stats]", callback_data="pm_stats")],
                    [InlineKeyboardButton(text="[🔙 Back]", callback_data="refresh_main")],
                    [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
                ])
            ),
            "live_manager": (
                "🔥 <b>ArcX | Live Manager</b>\\n\\n"
                "Live stream automation system:\\n\\n",
                InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="[▶️ Start Monitoring]", callback_data="lm_start_monitoring")],
                    [InlineKeyboardButton(text="[⏹️ Stop Monitoring]", callback_data="lm_stop_monitoring")],
                    [InlineKeyboardButton(text="[⚙️ Select Channels]", callback_data="lm_select_channels")],
                    [InlineKeyboardButton(text="[🔙 Back]", callback_data="refresh_main")],
                    [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
                ])
            ),
            "analytics": (
                "🔥 <b>ArcX | Analytics</b>\\n\\n"
                "Comprehensive performance monitoring:\\n\\n",
                InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="[📊 Channel Data]", callback_data="an_channel_data")],
                    [InlineKeyboardButton(text="[💾 System Info]", callback_data="an_system_info")],
                    [InlineKeyboardButton(text="[⚡ Engine Status]", callback_data="an_engine_status")],
                    [InlineKeyboardButton(text="[🔙 Back]", callback_data="refresh_main")],
                    [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
                ])
            ),
            "emoji_reaction": (
                "🔥 <b>ArcX | Emoji Reaction</b>\\n\\n"
                "Automated emoji reaction system:\\n\\n",
                InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="[😀 React to Messages]", callback_data="er_react_messages")],
                    [InlineKeyboardButton(text="[⚙️ Reaction Settings]", callback_data="er_settings")],
                    [InlineKeyboardButton(text="[🔙 Back]", callback_data="refresh_main")],
                    [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
                ])
            ),
        }
        
        return menus.get(feature, ("❌ Feature not found", InlineKeyboardMarkup(inline_keyboard=[])))
    
    async def _show_help_menu(self, callback: CallbackQuery):
        """Show detailed help menu"""
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
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="[🔙 Back to Main]", callback_data="refresh_main")]
        ])
        
        await callback.message.edit_text(help_text, reply_markup=keyboard)
        await callback.answer("📚 Help documentation loaded")

    async def _handle_unknown_callback(self, callback: CallbackQuery):
        """Handle unknown or unregistered callbacks"""
        logger.warning(f"Unknown callback received: {callback.data}")
        try:
            await callback.answer("❌ Unknown command. Please use the menu buttons.", show_alert=True)
        except Exception as e:
            if "query is too old" in str(e) or "timeout expired" in str(e):
                logger.info("Ignoring expired unknown callback query")
            else:
                logger.error(f"Error answering unknown callback: {e}")