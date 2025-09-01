"""
Manual Boost Handler
Handles manual view boosting operations
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from core.config.config import Config
from core.database.unified_database import DatabaseManager
from core.bot.telegram_bot import TelegramBotCore
from ..states.states import ViewBoostStates
from telethon.tl import functions

logger = logging.getLogger(__name__)


class ManualBoostHandler:
    """Handler for manual view boosting"""
    
    def __init__(self, bot: Bot, db_manager: DatabaseManager, config: Config):
        self.bot = bot
        self.db = db_manager
        self.config = config
        self.bot_core = TelegramBotCore(config, db_manager)
        self._active_boosts = {}
        
    async def initialize(self):
        """Initialize manual boost handler"""
        try:
            await self.bot_core.initialize()
            logger.info("✅ Manual boost handler initialized")
        except Exception as e:
            logger.error(f"Failed to initialize manual boost handler: {e}")
            raise
    
    def register_handlers(self, dp: Dispatcher):
        """Register handlers with dispatcher"""
        # Manual boost specific callbacks
        dp.callback_query.register(
            self.handle_manual_boost_callback,
            lambda c: c.data.startswith('mb_')
        )
        
        logger.info("✅ Manual boost handlers registered")
    
    async def handle_manual_boost_callback(self, callback: CallbackQuery, state: FSMContext):
        """Handle manual boost callbacks"""
        try:
            callback_data = callback.data
            user_id = callback.from_user.id
            
            if callback_data == "mb_by_link":
                await self._handle_boost_by_link(callback, state)
            elif callback_data == "mb_select_channel":
                await self._handle_select_channel(callback, state)
            elif callback_data == "mb_quick_boost":
                await self._handle_quick_boost(callback, state)
            elif callback_data == "mb_campaigns":
                await self._handle_view_campaigns(callback, state)
            elif callback_data == "mb_confirm_start":
                await self._handle_confirm_start(callback, state)
            elif callback_data == "mb_help_format":
                await self._handle_help_format(callback, state)
            elif callback_data == "mb_help_link":
                await self._handle_help_link(callback, state)
            elif callback_data.startswith("mb_channel_"):
                await self._handle_channel_selected(callback, state)
            elif callback_data.startswith("mb_quick_"):
                await self._handle_quick_channel(callback, state)
            else:
                await callback.answer("❌ Unknown manual boost action", show_alert=True)
                
        except Exception as e:
            logger.error(f"Error in manual boost callback: {e}")
            await callback.answer("❌ An error occurred", show_alert=True)
    
    async def _handle_boost_by_link(self, callback: CallbackQuery, state: FSMContext):
        """Handle boost by message link"""
        try:
            text = """
🔗 <b>Boost by Message Link</b>

Send me the Telegram message link you want to boost views for.

<b>📝 Supported Link Formats:</b>
• https://t.me/channelname/123
• https://telegram.me/channelname/123
• @channelname/123
• channelname/123

<b>📋 Requirements:</b>
• You must have access to the channel
• Message must be from one of your channels
• Link must be valid and accessible

Please send the message link:
            """
            
            keyboard = self._get_boost_by_link_keyboard()
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await state.set_state(ViewBoostStates.waiting_for_message_link)
            await callback.answer("🔗 Please send message link")
            
        except Exception as e:
            logger.error(f"Error in boost by link: {e}")
            await callback.answer("❌ Failed to start boost by link", show_alert=True)
    
    async def _handle_select_channel(self, callback: CallbackQuery, state: FSMContext):
        """Handle select channel for boosting"""
        try:
            user_id = callback.from_user.id
            
            # Get user channels
            channels = await self.db.get_user_channels(user_id)
            if not channels:
                await callback.message.edit_text(
                    "📭 <b>No Channels Available</b>\n\n"
                    "Please add channels first before manual boosting.",
                    reply_markup=self._get_no_channels_keyboard()
                )
                return
            
            text = f"""
📋 <b>Select Channel to Boost</b>

Choose a channel to boost views for its recent posts.

<b>📊 Available Channels:</b> {len(channels)}

Select a channel below to see its recent posts:
            """
            
            keyboard = self._get_channel_selection_keyboard(channels)
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("📋 Select channel to boost")
            
        except Exception as e:
            logger.error(f"Error in select channel: {e}")
            await callback.answer("❌ Failed to load channels", show_alert=True)
    
    async def _handle_quick_boost(self, callback: CallbackQuery, state: FSMContext):
        """Handle quick boost setup"""
        try:
            user_id = callback.from_user.id
            
            # Get user channels
            channels = await self.db.get_user_channels(user_id)
            if not channels:
                await callback.message.edit_text(
                    "📭 <b>No Channels Available</b>\n\n"
                    "Please add channels first before quick boosting.",
                    reply_markup=self._get_no_channels_keyboard()
                )
                return
            
            text = f"""
🚀 <b>Quick Boost</b>

Instantly boost the latest post from your channels with default settings.

<b>⚡ Quick Boost Features:</b>
• Boost latest post immediately
• Use default boost amount (500 views)
• Smart account selection
• Natural timing patterns
• Instant execution

<b>📊 Available Channels:</b> {len(channels)}

Select a channel for quick boost:
            """
            
            keyboard = self._get_quick_boost_keyboard(channels)
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("🚀 Quick boost options loaded")
            
        except Exception as e:
            logger.error(f"Error in quick boost: {e}")
            await callback.answer("❌ Failed to load quick boost", show_alert=True)
    
    async def _handle_view_campaigns(self, callback: CallbackQuery, state: FSMContext):
        """Handle view manual campaigns"""
        try:
            user_id = callback.from_user.id
            
            # Get manual campaigns
            campaigns = await self.db.fetch_all(
                """
                SELECT vbc.*, c.title as channel_title, c.username as channel_username
                FROM view_boost_campaigns vbc
                JOIN channels c ON vbc.channel_id = c.id
                WHERE vbc.user_id = $1 AND vbc.campaign_type = 'manual'
                ORDER BY vbc.created_at DESC
                LIMIT 15
                """,
                user_id
            )
            
            if not campaigns:
                await callback.message.edit_text(
                    "📭 <b>No Manual Campaigns</b>\n\n"
                    "You haven't created any manual boost campaigns yet.",
                    reply_markup=self._get_no_campaigns_keyboard()
                )
                return
            
            text = f"👆 <b>Manual Boost Campaigns ({len(campaigns)})</b>\n\n"
            
            # Show campaigns grouped by status
            active_campaigns = [c for c in campaigns if c['status'] == 'active']
            completed_campaigns = [c for c in campaigns if c['status'] == 'completed']
            
            if active_campaigns:
                text += f"🟢 <b>Active Campaigns ({len(active_campaigns)}):</b>\n"
                for campaign in active_campaigns[:3]:
                    progress = 0
                    if campaign['target_views'] > 0:
                        progress = (campaign['current_views'] / campaign['target_views']) * 100
                    
                    text += (
                        f"• {campaign['channel_title']}: "
                        f"{campaign['current_views']:,}/{campaign['target_views']:,} ({progress:.1f}%)\n"
                    )
                text += "\n"
            
            if completed_campaigns:
                text += f"✅ <b>Recent Completed ({len(completed_campaigns[:3])}):</b>\n"
                for campaign in completed_campaigns[:3]:
                    text += (
                        f"• {campaign['channel_title']}: "
                        f"{campaign['current_views']:,} views completed\n"
                    )
            
            keyboard = self._get_campaigns_keyboard(campaigns[:5])
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer(f"👆 {len(campaigns)} manual campaigns loaded")
            
        except Exception as e:
            logger.error(f"Error viewing campaigns: {e}")
            await callback.answer("❌ Failed to load campaigns", show_alert=True)
    
    async def _handle_confirm_start(self, callback: CallbackQuery, state: FSMContext):
        """Handle confirm start boost"""
        try:
            user_data = await state.get_data()
            boost_params = user_data.get('boost_params')
            message_link = user_data.get('message_link')
            
            if not boost_params:
                await callback.answer("❌ Boost parameters not found", show_alert=True)
                return
            
            # Start the boost campaign
            result = await self._create_and_start_campaign(callback.from_user.id, boost_params, message_link)
            
            if result['success']:
                await callback.message.edit_text(
                    f"✅ <b>Boost Campaign Started!</b>\n\n"
                    f"📊 <b>Campaign Details:</b>\n"
                    f"• Campaign ID: {result['campaign_id']}\n"
                    f"• Target Views: {boost_params['views']:,}\n"
                    f"• Estimated Duration: {self._estimate_duration(boost_params['views'])} minutes\n"
                    f"• Accounts Used: {result['accounts_count']}\n\n"
                    f"🚀 Your boost is now running! Check progress in campaign stats.",
                    reply_markup=self._get_campaign_started_keyboard(result['campaign_id'])
                )
                
                await callback.answer("✅ Boost campaign started!")
            else:
                await callback.message.edit_text(
                    f"❌ <b>Failed to Start Campaign</b>\n\n"
                    f"Error: {result['error']}\n\n"
                    f"Please check your settings and try again.",
                    reply_markup=self._get_retry_campaign_keyboard()
                )
                
                await callback.answer("❌ Failed to start campaign", show_alert=True)
            
            # Clear state
            await state.clear()
            
        except Exception as e:
            logger.error(f"Error confirming start: {e}")
            await callback.answer("❌ Failed to start campaign", show_alert=True)
            await state.clear()
    
    async def _handle_channel_selected(self, callback: CallbackQuery, state: FSMContext):
        """Handle channel selection for manual boost"""
        try:
            # Extract channel ID
            channel_id = int(callback.data.split("_")[-1])
            
            # Get channel info and recent posts
            channel = await self.db.get_channel_by_id(channel_id)
            if not channel:
                await callback.answer("❌ Channel not found", show_alert=True)
                return
            
            # Get recent posts from the channel
            recent_posts = await self._get_recent_posts(channel, callback.from_user.id)
            
            if not recent_posts:
                await callback.message.edit_text(
                    f"📭 <b>No Recent Posts</b>\n\n"
                    f"Channel: <b>{channel['title']}</b>\n\n"
                    f"No recent posts found or unable to access channel messages.\n"
                    f"Please check channel permissions and try again.",
                    reply_markup=self._get_back_to_selection_keyboard()
                )
                return
            
            text = f"""
📋 <b>{channel['title']}</b>

Recent posts available for boosting:

"""
            
            for i, post in enumerate(recent_posts[:5], 1):
                post_text = post['text'][:50] + "..." if len(post['text']) > 50 else post['text']
                text += (
                    f"<b>{i}.</b> {post_text}\n"
                    f"   📅 {post['date'].strftime('%m/%d %H:%M')} • "
                    f"👁️ {post.get('views', 0):,} views\n\n"
                )
            
            text += "Select a post to boost or set custom parameters:"
            
            keyboard = self._get_posts_keyboard(channel_id, recent_posts[:3])
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer(f"📋 {len(recent_posts)} posts loaded")
            
        except Exception as e:
            logger.error(f"Error in channel selected: {e}")
            await callback.answer("❌ Failed to load channel posts", show_alert=True)
    
    async def _handle_quick_channel(self, callback: CallbackQuery, state: FSMContext):
        """Handle quick boost for specific channel"""
        try:
            # Extract channel ID
            channel_id = int(callback.data.split("_")[-1])
            
            # Get channel info
            channel = await self.db.get_channel_by_id(channel_id)
            if not channel:
                await callback.answer("❌ Channel not found", show_alert=True)
                return
            
            # Show progress message
            await callback.message.edit_text(
                f"🚀 <b>Starting Quick Boost</b>\n\n"
                f"Channel: <b>{channel['title']}</b>\n"
                f"Finding latest post and starting boost...\n\n"
                f"⏳ Please wait...",
                reply_markup=None
            )
            
            # Execute quick boost
            result = await self._execute_quick_boost(channel, callback.from_user.id)
            
            if result['success']:
                await callback.message.edit_text(
                    f"✅ <b>Quick Boost Started!</b>\n\n"
                    f"📋 <b>Details:</b>\n"
                    f"• Channel: {channel['title']}\n"
                    f"• Message ID: {result['message_id']}\n"
                    f"• Target Views: {result['target_views']:,}\n"
                    f"• Campaign ID: {result['campaign_id']}\n\n"
                    f"🚀 Your quick boost is now running!",
                    reply_markup=self._get_campaign_started_keyboard(result['campaign_id'])
                )
                
                await callback.answer("✅ Quick boost started!")
            else:
                await callback.message.edit_text(
                    f"❌ <b>Quick Boost Failed</b>\n\n"
                    f"Error: {result['error']}\n\n"
                    f"Please try manual boost instead.",
                    reply_markup=self._get_retry_quick_keyboard()
                )
                
                await callback.answer("❌ Quick boost failed", show_alert=True)
            
        except Exception as e:
            logger.error(f"Error in quick channel boost: {e}")
            await callback.answer("❌ Failed to execute quick boost", show_alert=True)
    
    async def _handle_help_format(self, callback: CallbackQuery, state: FSMContext):
        """Show help for boost parameter format"""
        try:
            help_text = """
❓ <b>Boost Parameters Help</b>

<b>📝 Parameter Format:</b>
<code>views=1000 delay=5-10 accounts=all</code>

<b>🎯 Available Parameters:</b>

<b>views</b> (required)
• Number of views to boost
• Range: 1 to 100,000
• Example: <code>views=500</code>

<b>delay</b> (optional)
• Delay between boosts in seconds
• Format: min-max or single value
• Default: 2-8 seconds
• Example: <code>delay=3-7</code>

<b>accounts</b> (optional)
• Which accounts to use
• Options: all, random, count
• Default: all
• Example: <code>accounts=5</code>

<b>📋 Complete Examples:</b>
• <code>views=1000</code>
• <code>views=500 delay=10</code>
• <code>views=2000 delay=5-15 accounts=10</code>
• <code>views=750 delay=3</code>
            """
            
            keyboard = self._get_help_back_keyboard()
            
            await callback.message.edit_text(help_text, reply_markup=keyboard)
            await callback.answer("📚 Parameter format help loaded")
            
        except Exception as e:
            logger.error(f"Error showing format help: {e}")
            await callback.answer("❌ Failed to load help", show_alert=True)
    
    async def _handle_help_link(self, callback: CallbackQuery, state: FSMContext):
        """Show help for message link format"""
        try:
            help_text = """
❓ <b>Message Link Help</b>

<b>📝 How to Get Message Links:</b>

<b>1. From Telegram App:</b>
• Open the message you want to boost
• Tap and hold the message
• Select "Copy Link"
• Paste the link in this bot

<b>2. From Telegram Web:</b>
• Right-click the message
• Select "Copy Message Link"
• Paste the link here

<b>🔗 Supported Link Formats:</b>
• <code>https://t.me/channelname/123</code>
• <code>https://telegram.me/channelname/123</code>
• <code>@channelname/123</code>
• <code>channelname/123</code>

<b>📋 Requirements:</b>
• Channel must be in your channel list
• Message must be accessible
• You need appropriate permissions

<b>💡 Tips:</b>
• Use public channel links when possible
• Ensure the message ID is correct
• Check that the channel is active
            """
            
            keyboard = self._get_help_back_keyboard()
            
            await callback.message.edit_text(help_text, reply_markup=keyboard)
            await callback.answer("📚 Message link help loaded")
            
        except Exception as e:
            logger.error(f"Error showing link help: {e}")
            await callback.answer("❌ Failed to load help", show_alert=True)
    
    async def _get_recent_posts(self, channel: Dict[str, Any], user_id: int) -> List[Dict[str, Any]]:
        """Get recent posts from channel"""
        try:
            # Get user accounts
            accounts = await self.db.get_user_accounts(user_id, active_only=True)
            if not accounts:
                return []
            
            # Try with first available account
            client = await self.bot_core.get_client(accounts[0]['id'])
            if not client:
                return []
            
            # Check rate limits
            if not await self.bot_core.check_rate_limit(accounts[0]['id']):
                return []
            
            # Get recent messages
            messages = await client.get_messages(channel['channel_id'], limit=10)
            
            # Update rate limiter
            await self.bot_core.increment_rate_limit(accounts[0]['id'])
            
            # Format posts
            posts = []
            for message in messages:
                if message.date:
                    posts.append({
                        'message_id': message.id,
                        'text': message.text or '[Media]',
                        'date': message.date.replace(tzinfo=None),
                        'views': getattr(message, 'views', 0)
                    })
            
            return posts
            
        except Exception as e:
            logger.error(f"Error getting recent posts: {e}")
            return []
    
    async def _create_and_start_campaign(self, user_id: int, boost_params: Dict[str, Any], 
                                       message_link: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create and start boost campaign"""
        try:
            # Determine channel and message
            if message_link:
                # Find channel by name
                channel = await self.db.fetch_one(
                    "SELECT * FROM channels WHERE user_id = $1 AND username = $2",
                    user_id, message_link['channel_name']
                )
                if not channel:
                    return {'success': False, 'error': 'Channel not found in your channel list'}
                
                message_id = message_link['message_id']
            else:
                return {'success': False, 'error': 'Message information required'}
            
            # Create campaign
            campaign_id = await self.db.create_view_boost_campaign(
                user_id, channel['id'], message_id, boost_params['views'], 'manual'
            )
            
            if not campaign_id:
                return {'success': False, 'error': 'Failed to create campaign'}
            
            # Get available accounts
            accounts = await self.db.get_user_accounts(user_id, active_only=True)
            if not accounts:
                return {'success': False, 'error': 'No active accounts available'}
            
            # Start boost process
            boost_task = asyncio.create_task(
                self._execute_manual_boost(campaign_id, boost_params, accounts)
            )
            
            # Store task reference
            self._active_boosts[campaign_id] = boost_task
            
            return {
                'success': True,
                'campaign_id': campaign_id,
                'accounts_count': len(accounts)
            }
            
        except Exception as e:
            logger.error(f"Error creating and starting campaign: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _execute_quick_boost(self, channel: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """Execute quick boost for channel"""
        try:
            # Get latest post
            recent_posts = await self._get_recent_posts(channel, user_id)
            if not recent_posts:
                return {'success': False, 'error': 'No recent posts found'}
            
            latest_post = recent_posts[0]
            
            # Default quick boost parameters
            boost_params = {
                'views': 500,
                'delay_min': 3,
                'delay_max': 8,
                'accounts': 'all'
            }
            
            # Create campaign
            campaign_id = await self.db.create_view_boost_campaign(
                user_id, channel['id'], latest_post['message_id'], boost_params['views'], 'manual'
            )
            
            if not campaign_id:
                return {'success': False, 'error': 'Failed to create campaign'}
            
            # Get accounts
            accounts = await self.db.get_user_accounts(user_id, active_only=True)
            if not accounts:
                return {'success': False, 'error': 'No active accounts available'}
            
            # Start boost
            boost_task = asyncio.create_task(
                self._execute_manual_boost(campaign_id, boost_params, accounts)
            )
            
            self._active_boosts[campaign_id] = boost_task
            
            return {
                'success': True,
                'campaign_id': campaign_id,
                'message_id': latest_post['message_id'],
                'target_views': boost_params['views']
            }
            
        except Exception as e:
            logger.error(f"Error executing quick boost: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _execute_manual_boost(self, campaign_id: int, boost_params: Dict[str, Any], 
                                  accounts: List[Dict[str, Any]]):
        """Execute manual boost campaign"""
        try:
            target_views = boost_params['views']
            delay_min = boost_params['delay_min']
            delay_max = boost_params['delay_max']
            
            # Get campaign details
            campaign = await self.db.fetch_one(
                "SELECT * FROM view_boost_campaigns WHERE id = $1",
                campaign_id
            )
            
            if not campaign:
                return
            
            current_views = 0
            
            # Execute boost in batches
            batch_size = min(20, len(accounts))
            
            while current_views < target_views:
                # Select accounts for this batch
                batch_accounts = accounts[:batch_size]
                
                # Execute batch
                batch_success = 0
                for account in batch_accounts:
                    if current_views >= target_views:
                        break
                    
                    try:
                        success = await self._boost_single_view_manual(campaign, account)
                        if success:
                            batch_success += 1
                            current_views += 1
                        
                        # Delay between boosts
                        import random
                        delay = random.uniform(delay_min, delay_max)
                        await asyncio.sleep(delay)
                        
                    except Exception as e:
                        logger.error(f"Error in manual boost: {e}")
                
                # Update campaign progress
                await self.db.update_campaign_progress(campaign_id, current_views)
                
                # Check if we should continue
                if current_views >= target_views:
                    await self.db.update_campaign_progress(campaign_id, current_views, 'completed')
                    break
                
                # Wait before next batch
                await asyncio.sleep(10)
            
            # Clean up task reference
            if campaign_id in self._active_boosts:
                del self._active_boosts[campaign_id]
            
        except Exception as e:
            logger.error(f"Error executing manual boost: {e}")
            await self.db.update_campaign_progress(campaign_id, None, 'failed')
    
    async def _boost_single_view_manual(self, campaign: Dict[str, Any], account: Dict[str, Any]) -> bool:
        """Boost single view manually"""
        try:
            client = await self.bot_core.get_client(account['id'])
            if not client:
                return False
            
            # Check rate limits
            if not await self.bot_core.check_rate_limit(account['id']):
                return False
            
            # Get channel entity
            channel_entity = await client.get_entity(campaign['channel_id'])
            
            # Boost view
            result = await client(functions.messages.GetMessagesViewsRequest(
                peer=channel_entity,
                id=[campaign['message_id']],
                increment=True
            ))
            
            # Update rate limiter
            await self.bot_core.increment_rate_limit(account['id'])
            
            # Log success
            await self.db.log_view_boost(
                campaign['id'],
                account['id'],
                1,
                True,
                None
            )
            
            return True
            
        except Exception as e:
            # Log failure
            await self.db.log_view_boost(
                campaign['id'],
                account['id'],
                0,
                False,
                str(e)
            )
            logger.error(f"Error boosting single view manually: {e}")
            return False
    
    def _estimate_duration(self, views: int) -> int:
        """Estimate boost duration in minutes"""
        # Rough estimate: 1 view per 5 seconds average
        return max(1, views * 5 // 60)
    
    def _get_boost_by_link_keyboard(self):
        """Get boost by link keyboard"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        buttons = [
            [InlineKeyboardButton(text="❓ Link Format Help", callback_data="mb_help_link")],
            [InlineKeyboardButton(text="🔙 Back to Manual Boost", callback_data="vm_manual_boost")]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_channel_selection_keyboard(self, channels: List[Dict[str, Any]]):
        """Get channel selection keyboard"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        buttons = []
        
        # Add channels (max 8)
        for channel in channels[:8]:
            status = "🟢" if channel['is_active'] else "🔴"
            buttons.append([
                InlineKeyboardButton(
                    text=f"{status} {channel['title'][:30]}",
                    callback_data=f"mb_channel_{channel['id']}"
                )
            ])
        
        # Control buttons
        buttons.extend([
            [InlineKeyboardButton(text="🔙 Back to Manual Boost", callback_data="vm_manual_boost")]
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_quick_boost_keyboard(self, channels: List[Dict[str, Any]]):
        """Get quick boost keyboard"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        buttons = []
        
        # Add channels (max 6)
        for channel in channels[:6]:
            status = "🟢" if channel['is_active'] else "🔴"
            buttons.append([
                InlineKeyboardButton(
                    text=f"{status} 🚀 {channel['title'][:25]}",
                    callback_data=f"mb_quick_{channel['id']}"
                )
            ])
        
        # Control buttons
        buttons.extend([
            [InlineKeyboardButton(text="🔙 Back to Manual Boost", callback_data="vm_manual_boost")]
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_posts_keyboard(self, channel_id: int, posts: List[Dict[str, Any]]):
        """Get posts keyboard"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        buttons = []
        
        # Add posts (max 3)
        for i, post in enumerate(posts, 1):
            post_text = post['text'][:20] + "..." if len(post['text']) > 20 else post['text']
            buttons.append([
                InlineKeyboardButton(
                    text=f"{i}. {post_text}",
                    callback_data=f"mb_post_{channel_id}_{post['message_id']}"
                )
            ])
        
        # Control buttons
        buttons.extend([
            [InlineKeyboardButton(text="⚙️ Custom Parameters", callback_data=f"mb_custom_{channel_id}")],
            [InlineKeyboardButton(text="🔙 Back to Channels", callback_data="mb_select_channel")]
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_campaigns_keyboard(self, campaigns: List[Dict[str, Any]]):
        """Get campaigns keyboard"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        buttons = []
        
        # Add campaigns (max 5)
        for campaign in campaigns[:5]:
            status_emoji = {
                'active': '🟢',
                'paused': '⏸️',
                'completed': '✅',
                'failed': '❌'
            }.get(campaign['status'], '⚪')
            
            buttons.append([
                InlineKeyboardButton(
                    text=f"{status_emoji} {campaign['channel_title'][:25]}",
                    callback_data=f"vm_campaign_view_{campaign['id']}"
                )
            ])
        
        # Control buttons
        buttons.extend([
            [InlineKeyboardButton(text="➕ New Manual Boost", callback_data="vm_manual_boost")],
            [InlineKeyboardButton(text="🔙 Back to Manual Boost", callback_data="vm_manual_boost")]
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_campaign_started_keyboard(self, campaign_id: int):
        """Get campaign started keyboard"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        buttons = [
            [InlineKeyboardButton(text="📊 View Progress", callback_data=f"vm_campaign_view_{campaign_id}")],
            [InlineKeyboardButton(text="👆 New Manual Boost", callback_data="vm_manual_boost")],
            [InlineKeyboardButton(text="🔙 Back to View Manager", callback_data="view_manager")]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_help_back_keyboard(self):
        """Get help back keyboard"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        buttons = [
            [InlineKeyboardButton(text="🔙 Back to Manual Boost", callback_data="vm_manual_boost")]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_no_channels_keyboard(self):
        """Get no channels keyboard"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        buttons = [
            [InlineKeyboardButton(text="➕ Add Channel", callback_data="channel_management")],
            [InlineKeyboardButton(text="🔙 Back to View Manager", callback_data="view_manager")]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_no_campaigns_keyboard(self):
        """Get no campaigns keyboard"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        buttons = [
            [InlineKeyboardButton(text="🚀 Start First Boost", callback_data="mb_quick_boost")],
            [InlineKeyboardButton(text="🔙 Back to Manual Boost", callback_data="vm_manual_boost")]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_retry_campaign_keyboard(self):
        """Get retry campaign keyboard"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        buttons = [
            [InlineKeyboardButton(text="🔄 Try Again", callback_data="vm_manual_boost")],
            [InlineKeyboardButton(text="🔙 Back to View Manager", callback_data="view_manager")]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_retry_quick_keyboard(self):
        """Get retry quick keyboard"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        buttons = [
            [InlineKeyboardButton(text="🔄 Try Quick Boost Again", callback_data="mb_quick_boost")],
            [InlineKeyboardButton(text="👆 Try Manual Boost", callback_data="mb_select_channel")],
            [InlineKeyboardButton(text="🔙 Back to View Manager", callback_data="view_manager")]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_back_to_selection_keyboard(self):
        """Get back to selection keyboard"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        buttons = [
            [InlineKeyboardButton(text="🔙 Back to Channel Selection", callback_data="mb_select_channel")]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    async def shutdown(self):
        """Shutdown manual boost handler"""
        try:
            logger.info("⏹️ Shutting down manual boost handler...")
            
            # Cancel all active boosts
            for campaign_id, task in self._active_boosts.items():
                task.cancel()
            
            # Wait for tasks to finish
            if self._active_boosts:
                await asyncio.gather(*self._active_boosts.values(), return_exceptions=True)
            
            self._active_boosts.clear()
            
            logger.info("✅ Manual boost handler shut down")
            
        except Exception as e:
            logger.error(f"Error shutting down manual boost handler: {e}")
