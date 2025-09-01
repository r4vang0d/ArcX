"""
Channel Management Handler
Main handler for channel management operations
"""

import logging
from typing import Dict, Any, Optional
import re

from aiogram import Bot, Dispatcher
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from core.config.config import Config
from core.database.unified_database import DatabaseManager
from core.database.universal_access import UniversalDatabaseAccess
from .states import ChannelManagementStates
from .keyboards import ChannelManagementKeyboards
from .utils import ChannelValidator
from .handlers.add_channel import AddChannelHandler
from .handlers.list_channels import ListChannelsHandler

logger = logging.getLogger(__name__)


class ChannelManagementHandler:
    """Main channel management handler"""
    
    def __init__(self, bot: Bot, db_manager: DatabaseManager, config: Config):
        self.bot = bot
        self.db = db_manager
        self.config = config
        self.universal_db = UniversalDatabaseAccess(db_manager)
        self.keyboards = ChannelManagementKeyboards()
        self.validator = ChannelValidator(bot, db_manager, config)
        
        # Sub-handlers
        self.add_handler = AddChannelHandler(bot, db_manager, config)
        self.list_handler = ListChannelsHandler(bot, db_manager, config)
        
    async def initialize(self):
        """Initialize channel management handler"""
        try:
            await self.add_handler.initialize()
            await self.list_handler.initialize()
            logger.info("✅ Channel management handler initialized")
        except Exception as e:
            logger.error(f"Failed to initialize channel management handler: {e}")
            raise
    
    def register_handlers(self, dp: Dispatcher):
        """Register handlers with dispatcher"""
        # Register callback handlers
        # Callback registration handled by central inline_handler
        # dp.callback_query.register(
        #     self.handle_callback,
        #     lambda c: c.data.startswith('cm_')
        # )
        
        # Register FSM handlers
        dp.message.register(
            self.handle_channel_input,
            ChannelManagementStates.waiting_for_channel
        )
        
        # Register sub-handlers
        self.add_handler.register_handlers(dp)
        self.list_handler.register_handlers(dp)
        
        logger.info("✅ Channel management handlers registered")
    
    async def handle_callback(self, callback: CallbackQuery, state: FSMContext):
        """Handle channel management callbacks"""
        try:
            callback_data = callback.data
            user_id = callback.from_user.id
            
            # Ensure user exists
            await self.universal_db.ensure_user_exists(
                user_id, 
                callback.from_user.username,
                callback.from_user.first_name,
                callback.from_user.last_name
            )
            
            # Route to appropriate handler
            if callback_data == "cm_add_channel":
                await self._handle_add_channel_start(callback, state)
            elif callback_data == "cm_list_channels":
                await self._handle_list_channels(callback, state)
            elif callback_data == "cm_settings":
                await self._handle_channel_settings(callback, state)
            elif callback_data.startswith("cm_channel_"):
                await self._handle_channel_action(callback, state)
            elif callback_data.startswith("cm_delete_"):
                await self._handle_delete_channel(callback, state)
            elif callback_data.startswith("cm_edit_"):
                await self._handle_edit_channel(callback, state)
            elif callback_data == "cm_input_ready":
                await self._handle_input_ready(callback, state)
            elif callback_data == "cm_add_help":
                await self._handle_add_help(callback, state)
            elif callback_data == "cm_view_all_channels":
                await self._handle_view_all_channels(callback, state)
            elif callback_data == "cm_global_settings":
                await self._handle_global_settings(callback, state)
            elif callback_data.startswith("cm_confirm_delete_"):
                await self._handle_confirm_delete(callback, state)
            elif callback_data.startswith("cm_refresh_"):
                await self._handle_refresh_channel(callback, state)
            elif callback_data.startswith("cm_settings_"):
                await self._handle_individual_channel_settings(callback, state)
            else:
                await callback.answer("❌ Unknown channel management action", show_alert=True)
                
        except Exception as e:
            logger.error(f"Error in channel management callback: {e}")
            await callback.answer("❌ An error occurred. Please try again.", show_alert=True)
    
    async def _handle_add_channel_start(self, callback: CallbackQuery, state: FSMContext):
        """Start add channel process"""
        try:
            text = """
🎯 <b>Add New Channel</b>

Please provide your channel information. Supported formats:

📝 <b>Username:</b> @channelname or channelname
🔗 <b>Public Link:</b> https://t.me/channelname
🔒 <b>Private Invite:</b> https://t.me/joinchat/xxxxx
🔗 <b>New Private Link:</b> https://t.me/+xxxxx
🆔 <b>Channel ID:</b> -1001234567890
🔗 <b>Message Link:</b> https://t.me/c/1234567/123

<b>📋 Channel Types Supported:</b>
✅ Public channels
✅ Private channels (with invite link)
✅ Groups and supergroups
✅ Broadcast channels

<b>⚠️ Requirements:</b>
• You must be a member of the channel/group
• For best functionality, admin access is recommended
• The bot account must be able to access the channel

Please send your channel information:
            """
            
            keyboard = self.keyboards.get_add_channel_keyboard()
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await state.set_state(ChannelManagementStates.waiting_for_channel)
            await callback.answer("📝 Please provide channel information")
            
        except Exception as e:
            logger.error(f"Error starting add channel: {e}")
            await callback.answer("❌ Failed to start add channel process", show_alert=True)
    
    async def handle_channel_input(self, message: Message, state: FSMContext):
        """Handle channel input from user"""
        try:
            user_id = message.from_user.id
            channel_input = message.text.strip()
            
            # Show processing message
            processing_msg = await message.answer("🔍 Validating channel... Please wait.")
            
            # Validate and process channel
            result = await self.validator.validate_and_process_channel(user_id, channel_input)
            
            if result['success']:
                # Channel added successfully
                await processing_msg.edit_text(
                    f"✅ <b>Channel Added Successfully!</b>\n\n"
                    f"📋 <b>Title:</b> {result['channel_info']['title']}\n"
                    f"👥 <b>Members:</b> {result['channel_info'].get('member_count', 'Unknown')}\n"
                    f"🆔 <b>Channel ID:</b> {result['channel_info']['channel_id']}\n\n"
                    f"Your channel is now ready for view boosting and other operations!",
                    reply_markup=self.keyboards.get_channel_added_keyboard()
                )
                
                # Log success
                await self.db.log_system_event(
                    'INFO', 'channel_management',
                    f'Channel added successfully: {result["channel_info"]["title"]}',
                    {'user_id': user_id, 'channel_id': result['channel_info']['channel_id']}
                )
                
            else:
                # Channel validation failed
                await processing_msg.edit_text(
                    f"❌ <b>Failed to Add Channel</b>\n\n"
                    f"<b>Error:</b> {result['error']}\n\n"
                    f"Please check the channel information and try again.",
                    reply_markup=self.keyboards.get_add_channel_retry_keyboard()
                )
            
            # Clear state
            await state.clear()
            
        except Exception as e:
            logger.error(f"Error handling channel input: {e}")
            await message.answer(
                "❌ An error occurred while processing your channel. Please try again.",
                reply_markup=self.keyboards.get_back_to_menu_keyboard()
            )
            await state.clear()
    
    async def _handle_list_channels(self, callback: CallbackQuery, state: FSMContext):
        """Handle list channels request"""
        try:
            user_id = callback.from_user.id
            
            # Get user channels with statistics
            channels = await self.universal_db.get_user_channels_with_stats(user_id)
            
            if not channels:
                await callback.message.edit_text(
                    "📭 <b>No Channels Found</b>\n\n"
                    "You haven't added any channels yet. Add your first channel to get started!",
                    reply_markup=self.keyboards.get_no_channels_keyboard()
                )
                await callback.answer("📭 No channels found")
                return
            
            # Create channels list text
            text = f"📋 <b>Your Channels ({len(channels)})</b>\n\n"
            
            for i, channel in enumerate(channels[:10], 1):  # Limit to 10 channels
                status = "🟢" if channel['is_active'] else "🔴"
                campaigns = channel.get('campaign_stats', {}).get('total', 0)
                
                text += (
                    f"{status} <b>{i}. {channel['title']}</b>\n"
                    f"   👥 Members: {channel.get('member_count', 'Unknown')}\n"
                    f"   📈 Campaigns: {campaigns}\n"
                    f"   📅 Added: {channel['created_at'].strftime('%Y-%m-%d')}\n\n"
                )
            
            if len(channels) > 10:
                text += f"... and {len(channels) - 10} more channels"
            
            keyboard = self.keyboards.get_channels_list_keyboard(channels[:5])  # Show first 5 in keyboard
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer(f"📋 {len(channels)} channels loaded")
            
        except Exception as e:
            logger.error(f"Error listing channels: {e}")
            await callback.answer("❌ Failed to load channels", show_alert=True)
    
    async def _handle_channel_settings(self, callback: CallbackQuery, state: FSMContext):
        """Handle channel settings"""
        try:
            user_id = callback.from_user.id
            
            # Get user channels
            channels = await self.db.get_user_channels(user_id)
            
            if not channels:
                await callback.message.edit_text(
                    "📭 <b>No Channels to Configure</b>\n\n"
                    "Add channels first before configuring settings.",
                    reply_markup=self.keyboards.get_no_channels_keyboard()
                )
                return
            
            text = """
⚙️ <b>Channel Settings</b>

Configure settings for your channels:

• 🔄 Auto-refresh channel info
• 📊 Analytics preferences  
• 🚀 Default boost settings
• 🎭 Reaction preferences
• 🔔 Notification settings

Select a channel to configure:
            """
            
            keyboard = self.keyboards.get_settings_channels_keyboard(channels)
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("⚙️ Channel settings loaded")
            
        except Exception as e:
            logger.error(f"Error in channel settings: {e}")
            await callback.answer("❌ Failed to load settings", show_alert=True)
    
    async def _handle_channel_action(self, callback: CallbackQuery, state: FSMContext):
        """Handle specific channel actions"""
        try:
            # Extract channel ID from callback data
            channel_id = int(callback.data.split("_")[-1])
            
            # Get channel info
            channel = await self.db.get_channel_by_id(channel_id)
            if not channel:
                await callback.answer("❌ Channel not found", show_alert=True)
                return
            
            # Get recent statistics
            analytics = await self.db.get_analytics_data('channel', channel_id, limit=7)
            campaigns = await self.db.fetch_all(
                "SELECT * FROM view_boost_campaigns WHERE channel_id = $1 ORDER BY created_at DESC LIMIT 5",
                channel_id
            )
            
            text = f"""
📋 <b>{channel['title']}</b>

🆔 <b>Channel ID:</b> {channel['channel_id']}
👥 <b>Members:</b> {channel.get('member_count', 'Unknown')}
📅 <b>Added:</b> {channel['created_at'].strftime('%Y-%m-%d %H:%M')}
🔄 <b>Status:</b> {'Active' if channel['is_active'] else 'Inactive'}

📊 <b>Recent Activity:</b>
• Campaigns: {len(campaigns)}
• Analytics Points: {len(analytics)}

<b>What would you like to do?</b>
            """
            
            keyboard = self.keyboards.get_channel_actions_keyboard(channel_id)
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer(f"📋 {channel['title']} details")
            
        except Exception as e:
            logger.error(f"Error in channel action: {e}")
            await callback.answer("❌ Failed to load channel details", show_alert=True)
    
    async def _handle_delete_channel(self, callback: CallbackQuery, state: FSMContext):
        """Handle channel deletion"""
        try:
            # Extract channel ID
            channel_id = int(callback.data.split("_")[-1])
            user_id = callback.from_user.id
            
            # Get channel info
            channel = await self.db.get_channel_by_id(channel_id)
            if not channel or channel['user_id'] != user_id:
                await callback.answer("❌ Channel not found or access denied", show_alert=True)
                return
            
            # Check for active campaigns
            active_campaigns = await self.db.fetch_all(
                "SELECT COUNT(*) as count FROM view_boost_campaigns WHERE channel_id = $1 AND status = 'active'",
                channel_id
            )
            
            if active_campaigns and active_campaigns[0]['count'] > 0:
                await callback.message.edit_text(
                    f"⚠️ <b>Cannot Delete Channel</b>\n\n"
                    f"Channel <b>{channel['title']}</b> has active campaigns running.\n\n"
                    f"Please complete or stop all campaigns before deleting the channel.",
                    reply_markup=self.keyboards.get_back_to_channel_keyboard(channel_id)
                )
                return
            
            # Confirm deletion
            text = f"""
🗑️ <b>Delete Channel</b>

Are you sure you want to delete <b>{channel['title']}</b>?

⚠️ <b>This action will:</b>
• Remove the channel from your list
• Delete all campaign history
• Remove all analytics data
• This action cannot be undone!

Are you absolutely sure?
            """
            
            keyboard = self.keyboards.get_delete_confirmation_keyboard(channel_id)
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("⚠️ Confirm channel deletion")
            
        except Exception as e:
            logger.error(f"Error in delete channel: {e}")
            await callback.answer("❌ Failed to process deletion", show_alert=True)
    
    async def _handle_edit_channel(self, callback: CallbackQuery, state: FSMContext):
        """Handle channel editing"""
        try:
            # Extract channel ID
            channel_id = int(callback.data.split("_")[-1])
            
            # Get channel info
            channel = await self.db.get_channel_by_id(channel_id)
            if not channel:
                await callback.answer("❌ Channel not found", show_alert=True)
                return
            
            text = f"""
✏️ <b>Edit Channel Settings</b>

<b>Channel:</b> {channel['title']}

<b>Available Settings:</b>
• 📝 Update channel information
• 🔄 Refresh member count
• ⚙️ Configure boost settings
• 📊 Analytics preferences
• 🔔 Notification settings

Select what you'd like to edit:
            """
            
            keyboard = self.keyboards.get_edit_channel_keyboard(channel_id)
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("✏️ Edit channel options")
            
        except Exception as e:
            logger.error(f"Error in edit channel: {e}")
            await callback.answer("❌ Failed to load edit options", show_alert=True)
    
    async def get_user_channel_count(self, user_id: int) -> int:
        """Get count of user's channels"""
        try:
            result = await self.db.fetch_one(
                "SELECT COUNT(*) as count FROM channels WHERE user_id = $1 AND is_active = TRUE",
                user_id
            )
            return result['count'] if result else 0
        except Exception as e:
            logger.error(f"Error getting channel count: {e}")
            return 0
    
    async def get_channel_summary(self, user_id: int) -> Dict[str, Any]:
        """Get channel summary for user"""
        try:
            channels = await self.universal_db.get_user_channels_with_stats(user_id)
            
            total_channels = len(channels)
            active_channels = len([c for c in channels if c['is_active']])
            total_campaigns = sum(c.get('campaign_stats', {}).get('total', 0) for c in channels)
            
            return {
                'total_channels': total_channels,
                'active_channels': active_channels,
                'total_campaigns': total_campaigns,
                'channels': channels
            }
            
        except Exception as e:
            logger.error(f"Error getting channel summary: {e}")
            return {
                'total_channels': 0,
                'active_channels': 0,
                'total_campaigns': 0,
                'channels': []
            }
    
    async def _handle_input_ready(self, callback: CallbackQuery, state: FSMContext):
        """Handle input ready callback"""
        try:
            await callback.answer("📝 Ready for input")
            await state.set_state(ChannelManagementStates.waiting_for_channel)
        except Exception as e:
            logger.error(f"Error in input ready: {e}")
            await callback.answer("❌ Failed to prepare input", show_alert=True)
    
    async def _handle_add_help(self, callback: CallbackQuery, state: FSMContext):
        """Handle add channel help"""
        try:
            help_text = """
❓ <b>How to Add Channels</b>

<b>📝 Accepted Formats:</b>
• Username: @channelname
• Link: https://t.me/channelname
• ID: -1001234567890

<b>📋 Requirements:</b>
• You must be an admin of the channel
• Channel must be public or provide invite link
• Bot needs permission to read messages

<b>✅ Tips:</b>
• Use the exact username without spaces
• For private channels, add the bot as admin first
• Check channel privacy settings if errors occur
            """
            
            keyboard = self.keyboards.get_add_channel_keyboard()
            await callback.message.edit_text(help_text, reply_markup=keyboard)
            await callback.answer("❓ Help information loaded")
        except Exception as e:
            logger.error(f"Error in add help: {e}")
            await callback.answer("❌ Failed to load help", show_alert=True)
    
    async def _handle_view_all_channels(self, callback: CallbackQuery, state: FSMContext):
        """Handle view all channels"""
        try:
            user_id = callback.from_user.id
            channels = await self.universal_db.get_user_channels_with_stats(user_id)
            
            if not channels:
                await callback.message.edit_text(
                    "📭 <b>No Channels Found</b>\n\nAdd channels to see them here.",
                    reply_markup=self.keyboards.get_no_channels_keyboard()
                )
                return
            
            text = f"📋 <b>All Channels ({len(channels)})</b>\n\n"
            for i, channel in enumerate(channels, 1):
                status = "🟢" if channel['is_active'] else "🔴"
                text += f"{status} {i}. {channel['title'][:40]}\n"
            
            keyboard = self.keyboards.get_channels_list_keyboard(channels)
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer(f"📋 All {len(channels)} channels loaded")
        except Exception as e:
            logger.error(f"Error viewing all channels: {e}")
            await callback.answer("❌ Failed to load channels", show_alert=True)
    
    async def _handle_global_settings(self, callback: CallbackQuery, state: FSMContext):
        """Handle global settings"""
        try:
            text = """
⚙️ <b>Global Channel Settings</b>

Configure default settings for all channels:

• 🔄 Auto-refresh interval
• 📊 Default analytics settings
• 🚀 Default boost parameters
• 🎭 Default reaction settings
• 🔔 Global notifications

These settings apply to new channels by default.
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Auto-refresh Settings", callback_data="cm_global_refresh")],
                [InlineKeyboardButton(text="📊 Analytics Defaults", callback_data="cm_global_analytics")],
                [InlineKeyboardButton(text="🚀 Boost Defaults", callback_data="cm_global_boost")],
                [InlineKeyboardButton(text="🔙 Back to Settings", callback_data="cm_settings")]
            ])
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("⚙️ Global settings loaded")
        except Exception as e:
            logger.error(f"Error in global settings: {e}")
            await callback.answer("❌ Failed to load global settings", show_alert=True)
    
    async def _handle_confirm_delete(self, callback: CallbackQuery, state: FSMContext):
        """Handle confirmed channel deletion"""
        try:
            channel_id = int(callback.data.split("_")[-1])
            user_id = callback.from_user.id
            
            # Get channel info
            channel = await self.db.get_channel_by_id(channel_id)
            if not channel or channel['user_id'] != user_id:
                await callback.answer("❌ Channel not found or access denied", show_alert=True)
                return
            
            # Delete the channel
            await self.db.execute_query(
                "UPDATE channels SET is_active = FALSE, deleted_at = NOW() WHERE id = $1",
                channel_id
            )
            
            await callback.message.edit_text(
                f"✅ <b>Channel Deleted</b>\n\n"
                f"Channel <b>{channel['title']}</b> has been removed from your list.",
                reply_markup=self.keyboards.get_back_to_menu_keyboard()
            )
            
            await callback.answer("✅ Channel deleted successfully")
            
        except Exception as e:
            logger.error(f"Error confirming delete: {e}")
            await callback.answer("❌ Failed to delete channel", show_alert=True)
    
    async def _handle_refresh_channel(self, callback: CallbackQuery, state: FSMContext):
        """Handle refresh channel data"""
        try:
            channel_id = int(callback.data.split("_")[-1])
            
            # Refresh channel data
            channel = await self.db.get_channel_by_id(channel_id)
            if not channel:
                await callback.answer("❌ Channel not found", show_alert=True)
                return
            
            # Update last_updated timestamp
            await self.db.execute_query(
                "UPDATE channels SET updated_at = NOW() WHERE id = $1",
                channel_id
            )
            
            await callback.answer("🔄 Channel data refreshed")
            # Reload the channel details
            await self._handle_channel_action(callback, state)
            
        except Exception as e:
            logger.error(f"Error refreshing channel: {e}")
            await callback.answer("❌ Failed to refresh channel", show_alert=True)
    
    async def _handle_individual_channel_settings(self, callback: CallbackQuery, state: FSMContext):
        """Handle individual channel settings"""
        try:
            channel_id = int(callback.data.split("_")[-1])
            
            channel = await self.db.get_channel_by_id(channel_id)
            if not channel:
                await callback.answer("❌ Channel not found", show_alert=True)
                return
            
            text = f"""
⚙️ <b>Settings - {channel['title']}</b>

Configure specific settings for this channel:

• 🚀 Boost settings and defaults
• 📊 Analytics preferences
• 🎭 Reaction configuration
• 🔔 Notification settings
• ⏰ Schedule preferences
            """
            
            keyboard = self.keyboards.get_channel_settings_keyboard(channel_id)
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("⚙️ Channel settings loaded")
            
        except Exception as e:
            logger.error(f"Error in channel settings: {e}")
            await callback.answer("❌ Failed to load settings", show_alert=True)

    async def shutdown(self):
        """Shutdown channel management handler"""
        try:
            if hasattr(self.add_handler, 'shutdown'):
                await self.add_handler.shutdown()
            if hasattr(self.list_handler, 'shutdown'):
                await self.list_handler.shutdown()
            
            logger.info("✅ Channel management handler shut down")
        except Exception as e:
            logger.error(f"Error shutting down channel management handler: {e}")
