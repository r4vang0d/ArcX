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
            for prefix, handler in self.handlers.items():
                if callback_data.startswith(prefix):
                    logger.info(f"🔄 ROUTING: Callback '{callback_data}' routed to '{prefix}' handler")
                    if hasattr(handler, 'handle_callback'):
                        await handler.handle_callback(callback, state)
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
            "channel_management", "view_manager", "emoji_reactions",
            "analytics", "account_management", "system_health",
            "live_management", "view_monitoring", "help", "refresh_main"
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
                # Refresh main menu
                logger.info(f"🔄 MENU REFRESH: Refreshing main menu for user {user_id}")
                welcome_text = self._get_welcome_message(is_admin, username)
                keyboard = self._get_main_keyboard(is_admin)
                
                await callback.message.edit_text(welcome_text, reply_markup=keyboard)
                await callback.answer("🔄 Menu refreshed!")
                logger.info(f"🤖 RESPONSE: Main menu refreshed for user {user_id}")
                
            elif callback_data == "help":
                # Show help information
                logger.info(f"❓ HELP REQUEST: User {user_id} requested help menu")
                await self._show_help_menu(callback)
                
            elif callback_data == "help_manual":
                logger.info(f"📖 MANUAL REQUEST: User {user_id} requested user manual")
                await self._show_user_manual(callback)
                
            elif callback_data == "help_faq":
                logger.info(f"❓ FAQ REQUEST: User {user_id} requested FAQ")
                await self._show_faq(callback)
                
            elif callback_data == "help_troubleshoot":
                logger.info(f"🔧 TROUBLESHOOT REQUEST: User {user_id} requested troubleshooting")
                await self._show_troubleshooting(callback)
                
            elif callback_data == "system_health" and not is_admin:
                logger.warning(f"🚫 ACCESS DENIED: User {user_id} attempted to access admin-only system health")
                await callback.answer("❌ Admin access required!", show_alert=True)
                
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
            feature_name = feature.replace('_', ' ').title()
            
            logger.info(f"🎯 FEATURE ROUTING: Loading '{feature_name}' for user {user_id}")
            
            # Map callback data to handler methods
            feature_mapping = {
                "channel_management": "show_channel_management_menu",
                "view_manager": "show_view_manager_menu",
                "emoji_reactions": "show_emoji_reactions_menu",
                "analytics": "show_analytics_menu",
                "account_management": "show_account_management_menu",
                "live_management": "show_live_management_menu",
                "view_monitoring": "show_view_monitoring_menu",
                "system_health": "show_system_health_menu"
            }
            
            handler_method = feature_mapping.get(feature)
            if not handler_method:
                logger.warning(f"❌ FEATURE NOT FOUND: Feature '{feature}' not available")
                await callback.answer("❌ Feature not available", show_alert=True)
                return
            
            # Create feature menu text and keyboard
            menu_text, menu_keyboard = await self._get_feature_menu(feature)
            
            logger.info(f"🤖 FEATURE RESPONSE: Sending '{feature_name}' menu to user {user_id}")
            await callback.message.edit_text(menu_text, reply_markup=menu_keyboard)
            await callback.answer(f"📋 {feature_name} menu loaded")
            
        except Exception as e:
            logger.error(f"❌ FEATURE ERROR: Error routing to feature '{feature}' for user {callback.from_user.id}: {e}")
            await callback.answer("❌ Feature temporarily unavailable", show_alert=True)
    
    async def _get_feature_menu(self, feature: str) -> tuple[str, InlineKeyboardMarkup]:
        """Generate menu text and keyboard for specific feature"""
        menus = {
            "channel_management": (
                "🎯 <b>Channel Management</b>\n\n"
                "Manage your Telegram channels and configure their settings.\n\n"
                "• Add new channels\n"
                "• View existing channels\n"
                "• Configure channel settings\n"
                "• Remove channels",
                InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Add Channel", callback_data="cm_add_channel")],
                    [InlineKeyboardButton(text="📋 My Channels", callback_data="cm_list_channels")],
                    [InlineKeyboardButton(text="⚙️ Channel Settings", callback_data="cm_settings")],
                    [InlineKeyboardButton(text="🔙 Back to Main", callback_data="refresh_main")]
                ])
            ),
            "view_manager": (
                "🚀 <b>View Boosting</b>\n\n"
                "Boost views on your channel posts automatically or manually.\n\n"
                "• Automatic view boosting\n"
                "• Manual boost campaigns\n"
                "• Schedule boost tasks\n"
                "• View boost statistics",
                InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🤖 Auto Boost", callback_data="vm_auto_boost")],
                    [InlineKeyboardButton(text="👆 Manual Boost", callback_data="vm_manual_boost")],
                    [InlineKeyboardButton(text="⏰ Schedule Boost", callback_data="vm_schedule")],
                    [InlineKeyboardButton(text="📊 Boost Stats", callback_data="vm_stats")],
                    [InlineKeyboardButton(text="🔙 Back to Main", callback_data="refresh_main")]
                ])
            ),
            "emoji_reactions": (
                "🎭 <b>Emoji Reactions</b>\n\n"
                "Add emoji reactions to posts automatically.\n\n"
                "• Configure reaction emojis\n"
                "• Set reaction schedules\n"
                "• Monitor reaction performance",
                InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="😊 Configure Emojis", callback_data="er_configure")],
                    [InlineKeyboardButton(text="⏰ Reaction Schedule", callback_data="er_schedule")],
                    [InlineKeyboardButton(text="📊 Reaction Stats", callback_data="er_stats")],
                    [InlineKeyboardButton(text="🔙 Back to Main", callback_data="refresh_main")]
                ])
            ),
            "analytics": (
                "📊 <b>Analytics Dashboard</b>\n\n"
                "View detailed statistics and performance metrics.\n\n"
                "• Channel performance\n"
                "• View boost analytics\n"
                "• Account activity\n"
                "• System performance",
                InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📈 Channel Stats", callback_data="an_channel_stats")],
                    [InlineKeyboardButton(text="🚀 Boost Analytics", callback_data="an_boost_stats")],
                    [InlineKeyboardButton(text="📱 Account Analytics", callback_data="an_account_stats")],
                    [InlineKeyboardButton(text="🔙 Back to Main", callback_data="refresh_main")]
                ])
            ),
            "account_management": (
                "📱 <b>Account Management</b>\n\n"
                "Manage multiple Telegram accounts for operations.\n\n"
                "• Add Telegram accounts\n"
                "• View account status\n"
                "• Configure account settings\n"
                "• Account health monitoring",
                InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Add Account", callback_data="am_add_account")],
                    [InlineKeyboardButton(text="📋 My Accounts", callback_data="am_list_accounts")],
                    [InlineKeyboardButton(text="⚙️ Account Settings", callback_data="am_settings")],
                    [InlineKeyboardButton(text="💚 Health Check", callback_data="am_health")],
                    [InlineKeyboardButton(text="🔙 Back to Main", callback_data="refresh_main")]
                ])
            ),
            "live_management": (
                "🎙️ <b>Live Stream Management</b>\n\n"
                "Automatically join and manage live streams.\n\n"
                "• Auto-join live streams\n"
                "• Manual stream control\n"
                "• Live stream monitoring\n"
                "• Voice call settings",
                InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🤖 Auto Join", callback_data="lm_auto_join")],
                    [InlineKeyboardButton(text="👆 Manual Join", callback_data="lm_manual_join")],
                    [InlineKeyboardButton(text="📊 Live Monitor", callback_data="lm_monitor")],
                    [InlineKeyboardButton(text="⚙️ Voice Settings", callback_data="lm_settings")],
                    [InlineKeyboardButton(text="🔙 Back to Main", callback_data="refresh_main")]
                ])
            ),
            "view_monitoring": (
                "👁️ <b>View Monitoring</b>\n\n"
                "Monitor view counts and engagement in real-time.\n\n"
                "• Real-time view tracking\n"
                "• View growth analytics\n"
                "• Engagement monitoring\n"
                "• Performance alerts",
                InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📊 Real-time Views", callback_data="vm_realtime")],
                    [InlineKeyboardButton(text="📈 Growth Analytics", callback_data="vm_growth")],
                    [InlineKeyboardButton(text="🎯 Engagement Monitor", callback_data="vm_engagement")],
                    [InlineKeyboardButton(text="🔔 Setup Alerts", callback_data="vm_alerts")],
                    [InlineKeyboardButton(text="🔙 Back to Main", callback_data="refresh_main")]
                ])
            ),
            "system_health": (
                "💚 <b>System Health Monitoring</b>\n\n"
                "Monitor bot performance and system status.\n\n"
                "• System performance metrics\n"
                "• Database health\n"
                "• Account status overview\n"
                "• Error monitoring",
                InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📊 Performance", callback_data="sh_performance")],
                    [InlineKeyboardButton(text="🗄️ Database Health", callback_data="sh_database")],
                    [InlineKeyboardButton(text="📱 Account Status", callback_data="sh_accounts")],
                    [InlineKeyboardButton(text="🚨 Error Monitor", callback_data="sh_errors")],
                    [InlineKeyboardButton(text="🔙 Back to Main", callback_data="refresh_main")]
                ])
            )
        }
        
        return menus.get(feature, ("❌ Feature not found", InlineKeyboardMarkup(inline_keyboard=[])))
    
    async def _show_help_menu(self, callback: CallbackQuery):
        """Show detailed help menu"""
        help_text = """
🆘 <b>Help & Support</b>

<b>🎯 Channel Management:</b>
Add your channels by username or invite link. The bot will validate and store channel information for future operations.

<b>🚀 View Boosting:</b>
Automatically boost views on your posts using multiple accounts. Configure timing, frequency, and targeting options.

<b>🎭 Emoji Reactions:</b>
Add authentic emoji reactions to posts. Choose from various emojis and set realistic timing patterns.

<b>📊 Analytics:</b>
Monitor your channel performance, view growth, and engagement metrics in real-time.

<b>📱 Account Management:</b>
Add multiple Telegram accounts for operations. Each account requires phone number and verification.

<b>🎙️ Live Management:</b>
Automatically join live streams and voice chats to boost participation numbers.

<b>💡 Tips:</b>
• Start with adding channels and accounts
• Use realistic timing to avoid detection
• Monitor system health regularly
• Check analytics for optimization

<b>🔧 Technical Support:</b>
Contact administrators for technical assistance.
        """
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📖 User Manual", callback_data="help_manual")],
            [InlineKeyboardButton(text="❓ FAQ", callback_data="help_faq")],
            [InlineKeyboardButton(text="🔧 Troubleshooting", callback_data="help_troubleshoot")],
            [InlineKeyboardButton(text="🔙 Back to Main", callback_data="refresh_main")]
        ])
        
        await callback.message.edit_text(help_text, reply_markup=keyboard)
        await callback.answer("📚 Help information loaded")
    
    async def _show_user_manual(self, callback: CallbackQuery):
        """Show user manual"""
        manual_text = """
📖 <b>User Manual</b>

<b>🎯 Getting Started:</b>
1. Add your Telegram channels using /start → Channel Management
2. Add Telegram accounts for operations in Account Management
3. Set up view boosting campaigns
4. Monitor performance with Analytics

<b>📋 Channel Management:</b>
• Use @username, t.me/username, or channel ID to add channels
• You must be an admin of the channel
• Channels are validated before being added

<b>🚀 View Boosting:</b>
• Auto Boost - Automatically boost new posts
• Manual Boost - Boost specific posts
• Use realistic timing to avoid detection

<b>📱 Account Management:</b>
• Add multiple Telegram accounts for operations
• Each account needs phone verification
• Accounts are rotated to distribute load

<b>💡 Best Practices:</b>
• Use natural timing patterns
• Don't boost immediately after posting
• Monitor account health regularly
• Check rate limits and adjust accordingly
        """
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❓ FAQ", callback_data="help_faq")],
            [InlineKeyboardButton(text="🔧 Troubleshooting", callback_data="help_troubleshoot")],
            [InlineKeyboardButton(text="🔙 Back to Help", callback_data="help")]
        ])
        
        await callback.message.edit_text(manual_text, reply_markup=keyboard)
        await callback.answer("📖 User manual loaded")
    
    async def _show_faq(self, callback: CallbackQuery):
        """Show frequently asked questions"""
        faq_text = """
❓ <b>Frequently Asked Questions</b>

<b>Q: Why can't I add my channel?</b>
A: Make sure you're an admin of the channel and it's public or you have the invite link.

<b>Q: How many accounts can I add?</b>
A: You can add up to 100 Telegram accounts per user.

<b>Q: Are the view boosts detectable?</b>
A: We use natural timing and account rotation to minimize detection risk.

<b>Q: How fast can I boost views?</b>
A: Recommended: 50-200 views per hour per channel for natural appearance.

<b>Q: What if my account gets rate limited?</b>
A: The bot automatically respects rate limits and rotates accounts.

<b>Q: Can I schedule boosts for later?</b>
A: Yes, use the Schedule Boost feature in View Manager.

<b>Q: How do emoji reactions work?</b>
A: Set up automatic emoji reactions that appear naturally after posts.

<b>Q: Is my data secure?</b>
A: All session data is encrypted and stored securely.

<b>Q: What's the success rate?</b>
A: Typical success rates are 90-95% depending on account health.
        """
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📖 User Manual", callback_data="help_manual")],
            [InlineKeyboardButton(text="🔧 Troubleshooting", callback_data="help_troubleshoot")],
            [InlineKeyboardButton(text="🔙 Back to Help", callback_data="help")]
        ])
        
        await callback.message.edit_text(faq_text, reply_markup=keyboard)
        await callback.answer("❓ FAQ loaded")
    
    async def _show_troubleshooting(self, callback: CallbackQuery):
        """Show troubleshooting guide"""
        troubleshoot_text = """
🔧 <b>Troubleshooting Guide</b>

<b>🚨 Common Issues & Solutions:</b>

<b>❌ "Failed to add channel"</b>
• Ensure you're an admin of the channel
• Check if the channel username is correct
• Try using the full t.me link instead

<b>❌ "Account authentication failed"</b>
• Check your phone number format (+1234567890)
• Ensure you have access to receive SMS/calls
• Try adding the account again

<b>❌ "View boost not working"</b>
• Check if accounts are active and healthy
• Verify rate limits aren't exceeded
• Ensure the message/post exists

<b>❌ "Rate limit exceeded"</b>
• Wait for the limit to reset (usually 24 hours)
• Use fewer concurrent operations
• Add more accounts to distribute load

<b>❌ "Unknown error occurred"</b>
• Check your internet connection
• Restart the bot using /start
• Contact support if issue persists

<b>💡 Performance Tips:</b>
• Keep accounts healthy with regular breaks
• Use realistic boost amounts (50-500 views)
• Monitor success rates in Analytics
• Spread operations across multiple accounts

<b>🔧 Support:</b>
If problems persist, contact the administrators with:
• Error message details
• What you were trying to do
• Screenshot if possible
        """
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📖 User Manual", callback_data="help_manual")],
            [InlineKeyboardButton(text="❓ FAQ", callback_data="help_faq")],
            [InlineKeyboardButton(text="🔙 Back to Help", callback_data="help")]
        ])
        
        await callback.message.edit_text(troubleshoot_text, reply_markup=keyboard)
        await callback.answer("🔧 Troubleshooting guide loaded")

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
            InlineKeyboardButton(text="📊 Analytics", callback_data="analytics"),
            InlineKeyboardButton(text="👁️ View Monitoring", callback_data="view_monitoring")
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
