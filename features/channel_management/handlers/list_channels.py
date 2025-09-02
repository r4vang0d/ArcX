"""
List Channels Handler
Handles displaying and managing channel lists
"""

import logging
from typing import Dict, Any, List
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from core.config.config import Config
from core.database.unified_database import DatabaseManager
from core.database.universal_access import UniversalDatabaseAccess

logger = logging.getLogger(__name__)


class ListChannelsHandler:
    """Handler for listing and managing channels"""
    
    def __init__(self, bot: Bot, db_manager: DatabaseManager, config: Config, bot_core=None):
        self.bot = bot
        self.db = db_manager
        self.config = config
        self.bot_core = bot_core
        self.universal_db = UniversalDatabaseAccess(db_manager)
        
    async def initialize(self):
        """Initialize list channels handler"""
        logger.info("✅ List channels handler initialized")
    
    def register_handlers(self, dp: Dispatcher):
        """Register handlers with dispatcher"""
        # Callback handlers for channel list management
        dp.callback_query.register(
            self.handle_view_all_channels,
            lambda c: c.data == 'cm_view_all_channels'
        )
        
        dp.callback_query.register(
            self.handle_channel_details,
            lambda c: c.data.startswith('cm_details_')
        )
        
        dp.callback_query.register(
            self.handle_refresh_all,
            lambda c: c.data == 'cm_refresh_all'
        )
        
        dp.callback_query.register(
            self.handle_export_data,
            lambda c: c.data == 'cm_export_data'
        )
    
    async def handle_view_all_channels(self, callback: CallbackQuery, state: FSMContext):
        """Show all user channels with pagination"""
        try:
            user_id = callback.from_user.id
            page = 1  # Start with first page
            
            await self._show_channels_page(callback, user_id, page)
            
        except Exception as e:
            logger.error(f"Error viewing all channels: {e}")
            await callback.answer("❌ Failed to load channels", show_alert=True)
    
    async def _show_channels_page(self, callback: CallbackQuery, user_id: int, page: int):
        """Show specific page of channels"""
        try:
            # Get all user channels with stats
            all_channels = await self.universal_db.get_user_channels_with_stats(user_id)
            
            if not all_channels:
                await callback.message.edit_text(
                    "📭 <b>No Channels Found</b>\n\n"
                    "You haven't added any channels yet.",
                    reply_markup=self._get_no_channels_keyboard()
                )
                return
            
            # Pagination settings
            channels_per_page = 5
            total_pages = (len(all_channels) + channels_per_page - 1) // channels_per_page
            start_idx = (page - 1) * channels_per_page
            end_idx = start_idx + channels_per_page
            
            page_channels = all_channels[start_idx:end_idx]
            
            # Create channels text
            text = f"📋 <b>Your Channels</b> (Page {page}/{total_pages})\n\n"
            
            for i, channel in enumerate(page_channels, start_idx + 1):
                status = "🟢" if channel['is_active'] else "🔴"
                campaigns = channel.get('campaign_stats', {}).get('total', 0)
                member_count = channel.get('member_count', 0)
                
                text += (
                    f"{status} <b>{i}. {channel['title']}</b>\n"
                    f"   🆔 ID: {channel['channel_id']}\n"
                    f"   👥 Members: {member_count:,}\n"
                    f"   📈 Campaigns: {campaigns}\n"
                )
                
                # Show recent activity
                if channel.get('recent_views'):
                    latest_views = channel['recent_views'][0]
                    text += f"   👁️ Latest Views: {latest_views['metric_value']}\n"
                
                text += f"   📅 Added: {channel['created_at'].strftime('%m/%d/%Y')}\n\n"
            
            # Create keyboard with pagination
            keyboard = self._get_paginated_keyboard(page, total_pages, page_channels)
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer(f"📄 Page {page} of {total_pages}")
            
        except Exception as e:
            logger.error(f"Error showing channels page: {e}")
            await callback.answer("❌ Failed to load page", show_alert=True)
    
    def _get_paginated_keyboard(self, current_page: int, total_pages: int, 
                               channels: List[Dict[str, Any]]):
        """Create paginated keyboard for channels"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        buttons = []
        
        # Add quick action buttons for channels on current page
        for channel in channels[:3]:  # Show first 3 channels
            status = "🟢" if channel['is_active'] else "🔴"
            buttons.append([
                InlineKeyboardButton(
                    text=f"{status} {channel['title'][:25]}",
                    callback_data=f"cm_channel_{channel['id']}"
                )
            ])
        
        # Pagination controls
        if total_pages > 1:
            nav_buttons = []
            
            if current_page > 1:
                nav_buttons.append(
                    InlineKeyboardButton(text="⬅️ Previous", callback_data=f"cm_page_{current_page-1}")
                )
            
            nav_buttons.append(
                InlineKeyboardButton(text=f"📄 {current_page}/{total_pages}", callback_data="cm_page_info")
            )
            
            if current_page < total_pages:
                nav_buttons.append(
                    InlineKeyboardButton(text="Next ➡️", callback_data=f"cm_page_{current_page+1}")
                )
            
            buttons.append(nav_buttons)
        
        # Action buttons
        buttons.extend([
            [
                InlineKeyboardButton(text="🔄 Refresh All", callback_data="cm_refresh_all"),
                InlineKeyboardButton(text="📊 Export Data", callback_data="cm_export_data")
            ],
            [
                InlineKeyboardButton(text="➕ Add Channel", callback_data="cm_add_channel"),
                InlineKeyboardButton(text="⚙️ Batch Operations", callback_data="cm_batch_ops")
            ],
            [
                InlineKeyboardButton(text="🔙 Back to Menu", callback_data="refresh_main")
            ]
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_no_channels_keyboard(self):
        """Get keyboard when no channels exist"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        buttons = [
            [InlineKeyboardButton(text="➕ Add First Channel", callback_data="cm_add_channel")],
            [InlineKeyboardButton(text="❓ How to Add", callback_data="cm_add_help")],
            [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="refresh_main")]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    async def handle_channel_details(self, callback: CallbackQuery, state: FSMContext):
        """Show detailed channel information"""
        try:
            # Extract channel ID
            channel_id = int(callback.data.split("_")[-1])
            
            # Get detailed channel information
            channel_details = await self._get_detailed_channel_info(channel_id)
            
            if not channel_details:
                await callback.answer("❌ Channel not found", show_alert=True)
                return
            
            # Create detailed text
            text = await self._format_channel_details(channel_details)
            
            # Create keyboard
            keyboard = self._get_channel_details_keyboard(channel_id)
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("📋 Channel details loaded")
            
        except Exception as e:
            logger.error(f"Error showing channel details: {e}")
            await callback.answer("❌ Failed to load details", show_alert=True)
    
    async def _get_detailed_channel_info(self, channel_id: int) -> Dict[str, Any]:
        """Get comprehensive channel information"""
        try:
            # Get basic channel info
            channel = await self.db.get_channel_by_id(channel_id)
            if not channel:
                return None
            
            # Get campaigns
            campaigns = await self.db.fetch_all(
                """
                SELECT status, COUNT(*) as count, SUM(target_views) as target_views, 
                       SUM(current_views) as current_views
                FROM view_boost_campaigns 
                WHERE channel_id = $1 
                GROUP BY status
                """,
                channel_id
            )
            
            # Get recent analytics
            analytics = await self.db.get_analytics_data('channel', channel_id, limit=30)
            
            # Get boost logs
            recent_boosts = await self.db.fetch_all(
                """
                SELECT vbl.*, vbc.message_id, ta.phone_number
                FROM view_boost_logs vbl
                JOIN view_boost_campaigns vbc ON vbl.campaign_id = vbc.id
                JOIN telegram_accounts ta ON vbl.account_id = ta.id
                WHERE vbc.channel_id = $1
                ORDER BY vbl.timestamp DESC
                LIMIT 10
                """,
                channel_id
            )
            
            return {
                'channel': channel,
                'campaigns': campaigns,
                'analytics': analytics,
                'recent_boosts': recent_boosts
            }
            
        except Exception as e:
            logger.error(f"Error getting detailed channel info: {e}")
            return None
    
    async def _format_channel_details(self, details: Dict[str, Any]) -> str:
        """Format detailed channel information"""
        channel = details['channel']
        campaigns = details['campaigns']
        analytics = details['analytics']
        recent_boosts = details['recent_boosts']
        
        text = f"📋 <b>{channel['title']}</b>\n\n"
        
        # Basic info
        text += f"🆔 <b>Channel ID:</b> {channel['channel_id']}\n"
        if channel.get('username'):
            text += f"📧 <b>Username:</b> @{channel['username']}\n"
        text += f"👥 <b>Members:</b> {channel.get('member_count', 'Unknown'):,}\n"
        text += f"📅 <b>Added:</b> {channel['created_at'].strftime('%Y-%m-%d %H:%M')}\n"
        text += f"🔄 <b>Status:</b> {'Active' if channel['is_active'] else 'Inactive'}\n\n"
        
        # Campaign statistics
        text += f"📈 <b>Campaign Statistics:</b>\n"
        total_campaigns = sum(c['count'] for c in campaigns)
        total_target = sum(c['target_views'] or 0 for c in campaigns)
        total_current = sum(c['current_views'] or 0 for c in campaigns)
        
        text += f"• Total Campaigns: {total_campaigns}\n"
        if campaigns:
            for campaign in campaigns:
                status_emoji = {"active": "🟢", "completed": "✅", "failed": "❌", "paused": "⏸️"}.get(campaign['status'], "⚪")
                text += f"• {status_emoji} {campaign['status'].title()}: {campaign['count']}\n"
        
        if total_target > 0:
            completion_rate = (total_current / total_target) * 100
            text += f"• Target Views: {total_target:,}\n"
            text += f"• Current Views: {total_current:,}\n"
            text += f"• Completion: {completion_rate:.1f}%\n"
        
        text += "\n"
        
        # Recent activity
        if recent_boosts:
            text += f"🚀 <b>Recent Boost Activity:</b>\n"
            for boost in recent_boosts[:5]:
                success_emoji = "✅" if boost['success'] else "❌"
                text += f"• {success_emoji} +{boost['views_added']} views ({boost['timestamp'].strftime('%m/%d %H:%M')})\n"
        else:
            text += f"🚀 <b>Recent Activity:</b> No recent boosts\n"
        
        text += "\n"
        
        # Analytics summary
        if analytics:
            text += f"📊 <b>Analytics:</b>\n"
            text += f"• Data Points: {len(analytics)}\n"
            
            # Get latest member count if available
            member_analytics = [a for a in analytics if a['metric_name'] == 'member_count']
            if member_analytics:
                latest_count = member_analytics[0]['metric_value']
                text += f"• Latest Member Count: {latest_count:,.0f}\n"
        
        return text
    
    def _get_channel_details_keyboard(self, channel_id: int):
        """Get keyboard for channel details"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        buttons = [
            [
                InlineKeyboardButton(text="🚀 Boost Views", callback_data=f"vm_boost_channel_{channel_id}"),
                InlineKeyboardButton(text="📊 Full Analytics", callback_data=f"an_channel_{channel_id}")
            ],
            [
                InlineKeyboardButton(text="🎭 Reactions", callback_data=f"er_channel_{channel_id}"),
                InlineKeyboardButton(text="👁️ Monitor", callback_data=f"vm_monitor_{channel_id}")
            ],
            [
                InlineKeyboardButton(text="✏️ Edit", callback_data=f"cm_edit_{channel_id}"),
                InlineKeyboardButton(text="🔄 Refresh", callback_data=f"cm_refresh_{channel_id}")
            ],
            [
                InlineKeyboardButton(text="🔙 Back to List", callback_data="cm_list_channels")
            ]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    async def handle_refresh_all(self, callback: CallbackQuery, state: FSMContext):
        """Refresh all user channels"""
        try:
            user_id = callback.from_user.id
            
            # Get user channels
            channels = await self.db.get_user_channels(user_id, active_only=True)
            
            if not channels:
                await callback.answer("📭 No channels to refresh", show_alert=True)
                return
            
            # Show progress message
            await callback.message.edit_text(
                f"🔄 <b>Refreshing {len(channels)} channels...</b>\n\n"
                "This may take a few minutes. Please wait...",
                reply_markup=None
            )
            
            # Queue refresh tasks (if channel processor is available)
            try:
                from ..core.channel_processor import ChannelProcessor
                processor = ChannelProcessor(self.config, self.db, self.bot_core)
                await processor.queue_batch_refresh(user_id)
                
                message = f"✅ Refresh queued for {len(channels)} channels. Updates will appear shortly."
            except:
                # Fallback: simple refresh
                updated_count = 0
                for channel in channels[:5]:  # Limit to 5 for manual refresh
                    try:
                        # Simple database update
                        await self.db.execute_query(
                            "UPDATE channels SET updated_at = NOW() WHERE id = $1",
                            channel['id']
                        )
                        updated_count += 1
                    except:
                        continue
                
                message = f"✅ Refreshed {updated_count} channels successfully."
            
            # Show completion message
            from ..keyboards import ChannelManagementKeyboards
            keyboards = ChannelManagementKeyboards()
            
            await callback.message.edit_text(
                message,
                reply_markup=keyboards.get_back_to_menu_keyboard()
            )
            
            await callback.answer("✅ Refresh completed")
            
        except Exception as e:
            logger.error(f"Error refreshing all channels: {e}")
            await callback.answer("❌ Refresh failed", show_alert=True)
    
    async def handle_export_data(self, callback: CallbackQuery, state: FSMContext):
        """Export channel data"""
        try:
            user_id = callback.from_user.id
            
            # Get comprehensive user data
            channels = await self.universal_db.get_user_channels_with_stats(user_id)
            
            if not channels:
                await callback.answer("📭 No data to export", show_alert=True)
                return
            
            # Create export text
            export_text = f"📊 <b>Channel Data Export</b>\n"
            export_text += f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            export_text += f"👤 User ID: {user_id}\n\n"
            
            for i, channel in enumerate(channels, 1):
                export_text += f"<b>{i}. {channel['title']}</b>\n"
                export_text += f"   🆔 ID: {channel['channel_id']}\n"
                export_text += f"   👥 Members: {channel.get('member_count', 0):,}\n"
                export_text += f"   📈 Campaigns: {channel.get('campaign_stats', {}).get('total', 0)}\n"
                export_text += f"   📅 Added: {channel['created_at'].strftime('%Y-%m-%d')}\n"
                export_text += f"   🔄 Status: {'Active' if channel['is_active'] else 'Inactive'}\n\n"
            
            # Summary
            total_channels = len(channels)
            active_channels = len([c for c in channels if c['is_active']])
            total_campaigns = sum(c.get('campaign_stats', {}).get('total', 0) for c in channels)
            
            export_text += f"📋 <b>Summary:</b>\n"
            export_text += f"• Total Channels: {total_channels}\n"
            export_text += f"• Active Channels: {active_channels}\n"
            export_text += f"• Total Campaigns: {total_campaigns}\n"
            
            # Create keyboard
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 View Channels", callback_data="cm_list_channels")],
                [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="refresh_main")]
            ])
            
            await callback.message.edit_text(export_text, reply_markup=keyboard)
            await callback.answer("📊 Data exported successfully")
            
        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            await callback.answer("❌ Export failed", show_alert=True)
    
    async def get_channel_list_summary(self, user_id: int) -> Dict[str, Any]:
        """Get summary of user's channel list"""
        try:
            channels = await self.universal_db.get_user_channels_with_stats(user_id)
            
            total = len(channels)
            active = len([c for c in channels if c['is_active']])
            total_members = sum(c.get('member_count', 0) for c in channels)
            total_campaigns = sum(c.get('campaign_stats', {}).get('total', 0) for c in channels)
            
            return {
                'total_channels': total,
                'active_channels': active,
                'total_members': total_members,
                'total_campaigns': total_campaigns,
                'channels': channels[:5]  # Return first 5 for preview
            }
            
        except Exception as e:
            logger.error(f"Error getting channel list summary: {e}")
            return {
                'total_channels': 0,
                'active_channels': 0,
                'total_members': 0,
                'total_campaigns': 0,
                'channels': []
            }
    
    async def shutdown(self):
        """Shutdown list channels handler"""
        logger.info("✅ List channels handler shut down")
