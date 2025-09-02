"""
Channel Management Handler - ArcX Bot
Universal link handler for any channel type with simplified management
"""

import asyncio
import logging
import uuid
import re
from typing import Dict, Any, List, Optional

from aiogram import Bot, Dispatcher
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup

from core.config.config import Config
from core.database.unified_database import DatabaseManager

logger = logging.getLogger(__name__)


class ChannelStates(StatesGroup):
    """FSM states for channel management"""
    waiting_for_channel_link = State()


class ChannelManagementHandler:
    """Simplified Channel Manager with universal link handler"""
    
    def __init__(self, bot: Bot, db_manager: DatabaseManager, config: Config, bot_core=None):
        self.bot = bot
        self.db = db_manager
        self.config = config
        self.bot_core = bot_core
        self._pending_channels = {}  # Store temporary channel data during setup
        
    async def initialize(self):
        """Initialize channel management handler"""
        try:
            logger.info("✅ Channel management handler initialized")
        except Exception as e:
            logger.error(f"Failed to initialize channel management handler: {e}")
            raise
    
    def register_handlers(self, dp: Dispatcher):
        """Register handlers with dispatcher"""
        # FSM message handlers
        dp.message.register(self.handle_channel_link_input, ChannelStates.waiting_for_channel_link)
        
        logger.info("✅ Channel management handlers registered")
    
    async def handle_callback(self, callback: CallbackQuery, state: FSMContext):
        """Handle channel management callbacks"""
        try:
            callback_data = callback.data
            user_id = callback.from_user.id
            
            # Ensure user exists in database
            await self._ensure_user_exists(callback.from_user)
            
            if callback_data == "cm_add_channel":
                await self._handle_add_channel(callback, state)
            elif callback_data == "cm_remove_channel":
                await self._handle_remove_channel(callback, state)
            elif callback_data == "cm_list_channels":
                await self._handle_list_channels(callback, state)
            elif callback_data == "cm_refresh":
                await self._handle_refresh_channels(callback, state)
            elif callback_data.startswith("cm_info_"):
                await self._handle_channel_info(callback, state)
            elif callback_data.startswith("cm_delete_"):
                await self._handle_delete_channel(callback, state)
            else:
                await callback.answer("❌ Unknown action", show_alert=True)
                
        except Exception as e:
            logger.error(f"Error in channel management callback: {e}")
            await callback.answer("❌ An error occurred", show_alert=True)
    
    async def _handle_add_channel(self, callback: CallbackQuery, state: FSMContext):
        """Start add channel process with universal link handler"""
        try:
            user_id = callback.from_user.id
            
            # Check channel limit
            channels = await self._get_user_channels(user_id)
            if len(channels) >= 50:  # Reasonable limit for channels
                await callback.message.edit_text(
                    "🔥 <b>ArcX | Channel Limit Reached</b>\\n\\n"
                    "You have reached the maximum limit of 50 channels.\\n"
                    "Remove some channels before adding new ones.",
                    reply_markup=self._get_back_keyboard()
                )
                await callback.answer("⚠️ Channel limit reached!")
                return
            
            text = """🔥 <b>ArcX | Add Channel</b>

<b>Universal Link Handler - Supports any channel type:</b>

📺 <b>Public Channels:</b>
• t.me/channel_name
• @channel_name

🔒 <b>Private Channels:</b>
• t.me/+abcdef123456
• t.me/joinchat/abcdef123456

🎬 <b>Video/Stream Links:</b>
• Links to specific videos or streams

Send any channel link and the bot will automatically detect and add it:
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="[🔙 Back]", callback_data="channel_manager")],
                [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
            ])
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await state.set_state(ChannelStates.waiting_for_channel_link)
            await callback.answer("📺 Send channel link")
            
        except Exception as e:
            logger.error(f"Error in add channel: {e}")
            await callback.answer("❌ Failed to start add channel", show_alert=True)
    
    async def handle_channel_link_input(self, message: Message, state: FSMContext):
        """Handle universal channel link input"""
        try:
            user_id = message.from_user.id
            link = message.text.strip()
            
            # Parse channel link with universal handler
            channel_data = await self._parse_channel_link(link)
            
            if not channel_data:
                await message.answer(
                    "❌ <b>Invalid Channel Link</b>\\n\\n"
                    "Please send a valid Telegram channel link:\\n"
                    "• t.me/channel_name\\n"
                    "• @channel_name\\n"
                    "• t.me/+invite_link\\n"
                    "• t.me/joinchat/invite_link",
                    reply_markup=self._get_retry_keyboard()
                )
                return
            
            # Check if channel already exists
            existing = await self.db.fetch_one(
                "SELECT id FROM telegram_channels WHERE channel_identifier = $1 AND user_id = $2",
                channel_data['identifier'], user_id
            )
            
            if existing:
                await message.answer(
                    f"❌ <b>Channel Already Added</b>\\n\\n"
                    f"Channel: {channel_data['title']}\\n"
                    f"Type: {channel_data['type']}\\n"
                    f"This channel is already in your list.",
                    reply_markup=self._get_retry_keyboard()
                )
                return
            
            # Generate unique channel ID
            channel_uuid = str(uuid.uuid4())[:8]
            
            # Save channel to database
            channel_id = await self.db.execute_query(
                """
                INSERT INTO telegram_channels 
                (user_id, channel_identifier, channel_title, channel_type, unique_id, original_link, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())
                RETURNING id
                """,
                user_id, channel_data['identifier'], channel_data['title'], 
                channel_data['type'], channel_uuid, link
            )
            
            text = f"""✅ <b>ArcX | Channel Added Successfully!</b>

<b>Channel Details:</b>
• Title: {channel_data['title']}
• Type: {channel_data['type'].title()}
• Unique ID: {channel_uuid}
• Members: {channel_data.get('members', 'Unknown')}
• Status: ✅ Ready for operations

Channel is available for all bot features!
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="[📋 View All Channels]", callback_data="cm_list_channels")],
                [InlineKeyboardButton(text="[➕ Add Another]", callback_data="cm_add_channel")],
                [InlineKeyboardButton(text="[🔙 Channel Manager]", callback_data="channel_manager")],
                [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
            ])
            
            await message.answer(text, reply_markup=keyboard)
            await state.clear()
            
        except Exception as e:
            logger.error(f"Error handling channel link: {e}")
            await message.answer("❌ Error processing channel link")
    
    async def _handle_remove_channel(self, callback: CallbackQuery, state: FSMContext):
        """Handle remove channel"""
        try:
            user_id = callback.from_user.id
            
            channels = await self._get_user_channels(user_id)
            if not channels:
                await callback.message.edit_text(
                    "🔥 <b>ArcX | No Channels Found</b>\\n\\n"
                    "You don't have any channels to remove.",
                    reply_markup=self._get_back_keyboard()
                )
                await callback.answer("ℹ️ No channels to remove")
                return
            
            text = "🔥 <b>ArcX | Remove Channel</b>\\n\\nSelect channel to remove:\\n\\n"
            
            buttons = []
            for i, channel in enumerate(channels[:10], 1):  # Show max 10
                button_text = f"[🗑️ {channel['channel_title'][:20]}...]"
                callback_data = f"cm_delete_{channel['id']}"
                buttons.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])
            
            buttons.extend([
                [InlineKeyboardButton(text="[🔙 Back]", callback_data="channel_manager")],
                [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
            ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("🗑️ Select channel to remove")
            
        except Exception as e:
            logger.error(f"Error in remove channel: {e}")
            await callback.answer("❌ Failed to load remove channel", show_alert=True)
    
    async def _handle_list_channels(self, callback: CallbackQuery, state: FSMContext):
        """Handle list channels with info popups"""
        try:
            user_id = callback.from_user.id
            
            channels = await self._get_user_channels(user_id)
            if not channels:
                await callback.message.edit_text(
                    "🔥 <b>ArcX | No Channels</b>\\n\\n"
                    "You haven't added any channels yet.\\n"
                    "Add your first channel to get started!",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="[➕ Add Channel]", callback_data="cm_add_channel")],
                        [InlineKeyboardButton(text="[🔙 Back]", callback_data="channel_manager")],
                        [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
                    ])
                )
                await callback.answer("ℹ️ No channels found")
                return
            
            text = f"🔥 <b>ArcX | Channel List</b>\\n\\nTotal Channels: {len(channels)}\\n\\n"
            
            buttons = []
            for i, channel in enumerate(channels[:10], 1):  # Show max 10
                title = channel['channel_title'][:15] + "..." if len(channel['channel_title']) > 15 else channel['channel_title']
                status = "✅" if channel['is_active'] else "❌"
                
                # Channel name button and info button in same row
                buttons.append([
                    InlineKeyboardButton(text=f"[{i}. {status} {title}]", callback_data=f"cm_select_{channel['id']}"),
                    InlineKeyboardButton(text="[ℹ️]", callback_data=f"cm_info_{channel['id']}")
                ])
            
            buttons.extend([
                [InlineKeyboardButton(text="[🔙 Back]", callback_data="channel_manager")],
                [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
            ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer(f"📋 {len(channels)} channels loaded")
            
        except Exception as e:
            logger.error(f"Error listing channels: {e}")
            await callback.answer("❌ Failed to load channels", show_alert=True)
    
    async def _handle_channel_info(self, callback: CallbackQuery, state: FSMContext):
        """Show detailed channel information popup"""
        try:
            channel_id = int(callback.data.split('_')[2])
            
            channel = await self.db.fetch_one(
                "SELECT * FROM telegram_channels WHERE id = $1", channel_id
            )
            
            if not channel:
                await callback.answer("❌ Channel not found", show_alert=True)
                return
            
            # Get channel stats
            stats = await self._get_channel_stats(channel)
            
            info_text = f"""📺 <b>Channel Information</b>

<b>Basic Details:</b>
• Title: {channel['channel_title']}
• Type: {channel['channel_type'].title()}
• Unique ID: {channel.get('unique_id', 'N/A')}
• Status: {"✅ Active" if channel['is_active'] else "❌ Inactive"}

<b>Channel Statistics:</b>
• Members: {stats.get('member_count', 'Unknown')}
• Total Views: {stats.get('total_views', 0)}
• Avg. Views: {stats.get('avg_views', 0)}
• Last Boosted: {stats.get('last_boost', 'Never')}

<b>Performance:</b>
• Success Rate: {stats.get('success_rate', 0)}%
• Total Operations: {stats.get('total_operations', 0)}
• Boost Count: {stats.get('boost_count', 0)}

<b>Technical Details:</b>
• Added: {channel['created_at'].strftime('%Y-%m-%d %H:%M')}
• Identifier: {channel['channel_identifier']}
• Original Link: {channel.get('original_link', 'N/A')}
            """
            
            await callback.answer(info_text, show_alert=True)
            
        except Exception as e:
            logger.error(f"Error showing channel info: {e}")
            await callback.answer("❌ Error loading channel info", show_alert=True)
    
    async def _handle_refresh_channels(self, callback: CallbackQuery, state: FSMContext):
        """Refresh channels list"""
        try:
            # Show channel manager menu again with fresh data
            text = "🔥 <b>ArcX | Channel Manager</b>\\n\\nUniversal channel management system:\\n\\n"
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="[➕ Add Channel]", callback_data="cm_add_channel")],
                [InlineKeyboardButton(text="[🗑️ Remove Channel]", callback_data="cm_remove_channel")],
                [InlineKeyboardButton(text="[📋 List Channels]", callback_data="cm_list_channels")],
                [InlineKeyboardButton(text="[🔄 Refresh Channels]", callback_data="cm_refresh")],
                [InlineKeyboardButton(text="[🔙 Back]", callback_data="refresh_main")],
                [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
            ])
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("🔄 Channels refreshed!")
            
        except Exception as e:
            logger.error(f"Error refreshing channels: {e}")
            await callback.answer("❌ Failed to refresh", show_alert=True)
    
    async def _handle_delete_channel(self, callback: CallbackQuery, state: FSMContext):
        """Handle channel deletion"""
        try:
            channel_id = int(callback.data.split('_')[2])
            
            # Get channel details
            channel = await self.db.fetch_one(
                "SELECT * FROM telegram_channels WHERE id = $1", channel_id
            )
            
            if not channel:
                await callback.answer("❌ Channel not found", show_alert=True)
                return
            
            # Delete from database
            await self.db.execute_query(
                "DELETE FROM telegram_channels WHERE id = $1", channel_id
            )
            
            text = f"""✅ <b>ArcX | Channel Removed</b>

Channel successfully removed:
• Title: {channel['channel_title']}
• Type: {channel['channel_type'].title()}
• Unique ID: {channel.get('unique_id', 'N/A')}

All associated data has been cleaned up.
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="[📋 View Remaining]", callback_data="cm_list_channels")],
                [InlineKeyboardButton(text="[🔙 Channel Manager]", callback_data="channel_manager")],
                [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
            ])
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("✅ Channel removed successfully!")
            
        except Exception as e:
            logger.error(f"Error deleting channel: {e}")
            await callback.answer("❌ Failed to remove channel", show_alert=True)
    
    async def _parse_channel_link(self, link: str) -> Optional[Dict[str, Any]]:
        """Universal link parser for any channel type"""
        try:
            link = link.strip()
            
            # Remove protocol if present
            if link.startswith('http://') or link.startswith('https://'):
                link = link.split('://', 1)[1]
            
            # Patterns for different channel types
            patterns = {
                'public_username': r't\.me/([a-zA-Z0-9_]+)$',
                'private_invite': r't\.me/\+([a-zA-Z0-9_-]+)$',
                'joinchat': r't\.me/joinchat/([a-zA-Z0-9_-]+)$',
                'username_direct': r'^@([a-zA-Z0-9_]+)$',
                'plain_username': r'^([a-zA-Z0-9_]+)$'
            }
            
            for channel_type, pattern in patterns.items():
                match = re.match(pattern, link)
                if match:
                    identifier = match.group(1)
                    
                    # Determine channel type and title
                    if channel_type in ['public_username', 'username_direct', 'plain_username']:
                        return {
                            'identifier': f"@{identifier}",
                            'title': identifier,
                            'type': 'public',
                            'link': link,
                            'members': await self._get_channel_member_count(f"@{identifier}")
                        }
                    else:
                        return {
                            'identifier': identifier,
                            'title': f"Private Channel ({identifier[:8]}...)",
                            'type': 'private',
                            'link': link,
                            'members': 'Private'
                        }
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing channel link: {e}")
            return None
    
    async def _get_channel_member_count(self, username: str) -> str:
        """Get member count for public channel"""
        try:
            # In a real implementation, this would use Telethon to get actual member count
            # For now, return placeholder
            return "Unknown"
        except Exception:
            return "Unknown"
    
    async def _get_channel_stats(self, channel: Dict[str, Any]) -> Dict[str, Any]:
        """Get channel statistics"""
        try:
            # Get basic stats from database
            stats = await self.db.fetch_one(
                """
                SELECT 
                    COUNT(*) as total_operations,
                    COALESCE(AVG(CASE WHEN success THEN 1 ELSE 0 END) * 100, 0) as success_rate,
                    COUNT(CASE WHEN operation_type = 'boost' THEN 1 END) as boost_count
                FROM channel_operations 
                WHERE channel_id = $1
                """,
                channel['id']
            )
            
            return {
                'member_count': channel.get('member_count', 'Unknown'),
                'total_views': channel.get('total_views', 0),
                'avg_views': channel.get('avg_views', 0),
                'last_boost': channel.get('last_boost', 'Never'),
                'success_rate': int(stats.get('success_rate', 0)) if stats else 0,
                'total_operations': stats.get('total_operations', 0) if stats else 0,
                'boost_count': stats.get('boost_count', 0) if stats else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting channel stats: {e}")
            return {}
    
    # Helper methods
    async def _get_user_channels(self, user_id: int) -> List[Dict[str, Any]]:
        """Get user's channels"""
        return await self.db.fetch_all(
            "SELECT * FROM telegram_channels WHERE user_id = $1 ORDER BY created_at DESC",
            user_id
        )
    
    async def _ensure_user_exists(self, user):
        """Ensure user exists in database"""
        await self.db.execute_query(
            """
            INSERT INTO users (user_id, username, first_name, last_name, first_seen, last_seen)
            VALUES ($1, $2, $3, $4, NOW(), NOW())
            ON CONFLICT (user_id) DO UPDATE SET 
                username = $2, last_seen = NOW()
            """,
            user.id, user.username, user.first_name, user.last_name
        )
    
    def _get_back_keyboard(self) -> InlineKeyboardMarkup:
        """Get back button keyboard"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="[🔙 Channel Manager]", callback_data="channel_manager")],
            [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
        ])
    
    def _get_retry_keyboard(self) -> InlineKeyboardMarkup:
        """Get retry keyboard"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="[🔄 Try Again]", callback_data="cm_add_channel")],
            [InlineKeyboardButton(text="[🔙 Back]", callback_data="channel_manager")]
        ])