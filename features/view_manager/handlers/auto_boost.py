"""
Auto Boost Handler
Handles automatic view boosting operations
"""

import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from core.config.config import Config
from core.database.unified_database import DatabaseManager
from core.bot.telegram_bot import TelegramBotCore
from telethon.tl import functions

logger = logging.getLogger(__name__)


class AutoBoostHandler:
    """Handler for automatic view boosting"""
    
    def __init__(self, bot: Bot, db_manager: DatabaseManager, config: Config):
        self.bot = bot
        self.db = db_manager
        self.config = config
        self.bot_core = TelegramBotCore(config, db_manager)
        self._monitoring_tasks = {}
        self._boost_workers = []
        self._running = False
        
    async def initialize(self):
        """Initialize auto boost handler"""
        try:
            await self.bot_core.initialize()
            await self._start_monitoring()
            self._running = True
            logger.info("✅ Auto boost handler initialized")
        except Exception as e:
            logger.error(f"Failed to initialize auto boost handler: {e}")
            raise
    
    def register_handlers(self, dp: Dispatcher):
        """Register handlers with dispatcher"""
        # Auto boost specific callbacks
        dp.callback_query.register(
            self.handle_auto_boost_callback,
            lambda c: c.data.startswith('ab_')
        )
        
        logger.info("✅ Auto boost handlers registered")
    
    async def handle_auto_boost_callback(self, callback: CallbackQuery, state: FSMContext):
        """Handle auto boost callbacks"""
        try:
            callback_data = callback.data
            user_id = callback.from_user.id
            
            if callback_data == "ab_setup":
                await self._handle_setup_auto_boost(callback, state)
            elif callback_data == "ab_campaigns":
                await self._handle_view_campaigns(callback, state)
            elif callback_data == "ab_pause_all":
                await self._handle_pause_all(callback, state)
            elif callback_data == "ab_resume_all":
                await self._handle_resume_all(callback, state)
            elif callback_data == "ab_settings":
                await self._handle_auto_settings(callback, state)
            else:
                await callback.answer("❌ Unknown auto boost action", show_alert=True)
                
        except Exception as e:
            logger.error(f"Error in auto boost callback: {e}")
            await callback.answer("❌ An error occurred", show_alert=True)
    
    async def _handle_setup_auto_boost(self, callback: CallbackQuery, state: FSMContext):
        """Handle auto boost setup"""
        try:
            user_id = callback.from_user.id
            
            # Get user channels
            channels = await self.db.get_user_channels(user_id)
            if not channels:
                await callback.message.edit_text(
                    "📭 <b>No Channels Available</b>\n\n"
                    "Please add channels first before setting up auto boosting.",
                    reply_markup=self._get_no_channels_keyboard()
                )
                return
            
            # Get user accounts
            accounts = await self.db.get_user_accounts(user_id, active_only=True)
            if not accounts:
                await callback.message.edit_text(
                    "📱 <b>No Accounts Available</b>\n\n"
                    "Please add Telegram accounts first before setting up auto boosting.",
                    reply_markup=self._get_no_accounts_keyboard()
                )
                return
            
            text = f"""
⚙️ <b>Setup Auto Boost</b>

Configure automatic view boosting for your channels.

<b>📊 Available Resources:</b>
• Channels: {len(channels)}
• Accounts: {len(accounts)}

<b>🤖 Auto Boost Features:</b>
• Monitor channels for new posts
• Automatically boost views within minutes
• Configurable boost amounts and timing
• Smart account rotation
• Natural-looking patterns

Select channels to enable auto boosting:
            """
            
            keyboard = self._get_setup_channels_keyboard(channels)
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("⚙️ Auto boost setup loaded")
            
        except Exception as e:
            logger.error(f"Error in setup auto boost: {e}")
            await callback.answer("❌ Failed to load setup", show_alert=True)
    
    async def _handle_view_campaigns(self, callback: CallbackQuery, state: FSMContext):
        """Handle view auto campaigns"""
        try:
            user_id = callback.from_user.id
            
            # Get auto campaigns
            campaigns = await self.db.fetch_all(
                """
                SELECT vbc.*, c.title as channel_title, c.username as channel_username
                FROM view_boost_campaigns vbc
                JOIN channels c ON vbc.channel_id = c.id
                WHERE vbc.user_id = $1 AND vbc.campaign_type = 'auto'
                ORDER BY vbc.created_at DESC
                LIMIT 10
                """,
                user_id
            )
            
            if not campaigns:
                await callback.message.edit_text(
                    "📭 <b>No Auto Campaigns</b>\n\n"
                    "You haven't set up any auto boost campaigns yet.",
                    reply_markup=self._get_no_campaigns_keyboard()
                )
                return
            
            text = f"🤖 <b>Auto Boost Campaigns ({len(campaigns)})</b>\n\n"
            
            for campaign in campaigns:
                status_emoji = {
                    'active': '🟢',
                    'paused': '⏸️', 
                    'completed': '✅',
                    'failed': '❌'
                }.get(campaign['status'], '⚪')
                
                progress = 0
                if campaign['target_views'] > 0:
                    progress = (campaign['current_views'] / campaign['target_views']) * 100
                
                text += (
                    f"{status_emoji} <b>{campaign['channel_title']}</b>\n"
                    f"   🎯 Progress: {campaign['current_views']:,}/{campaign['target_views']:,} ({progress:.1f}%)\n"
                    f"   📅 Created: {campaign['created_at'].strftime('%m/%d %H:%M')}\n\n"
                )
            
            keyboard = self._get_campaigns_keyboard(campaigns[:5])  # Show first 5 in keyboard
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer(f"🤖 {len(campaigns)} auto campaigns loaded")
            
        except Exception as e:
            logger.error(f"Error viewing campaigns: {e}")
            await callback.answer("❌ Failed to load campaigns", show_alert=True)
    
    async def _handle_pause_all(self, callback: CallbackQuery, state: FSMContext):
        """Handle pause all campaigns"""
        try:
            user_id = callback.from_user.id
            
            # Pause all active auto campaigns
            updated = await self.db.execute_query(
                """
                UPDATE view_boost_campaigns 
                SET status = 'paused', updated_at = NOW()
                WHERE user_id = $1 AND campaign_type = 'auto' AND status = 'active'
                """,
                user_id
            )
            
            await callback.answer("⏸️ All auto campaigns paused")
            await self._handle_view_campaigns(callback, state)
            
        except Exception as e:
            logger.error(f"Error pausing all campaigns: {e}")
            await callback.answer("❌ Failed to pause campaigns", show_alert=True)
    
    async def _handle_resume_all(self, callback: CallbackQuery, state: FSMContext):
        """Handle resume all campaigns"""
        try:
            user_id = callback.from_user.id
            
            # Resume all paused auto campaigns
            updated = await self.db.execute_query(
                """
                UPDATE view_boost_campaigns 
                SET status = 'active', updated_at = NOW()
                WHERE user_id = $1 AND campaign_type = 'auto' AND status = 'paused'
                """,
                user_id
            )
            
            await callback.answer("▶️ All auto campaigns resumed")
            await self._handle_view_campaigns(callback, state)
            
        except Exception as e:
            logger.error(f"Error resuming all campaigns: {e}")
            await callback.answer("❌ Failed to resume campaigns", show_alert=True)
    
    async def _handle_auto_settings(self, callback: CallbackQuery, state: FSMContext):
        """Handle auto boost settings"""
        try:
            user_id = callback.from_user.id
            
            # Get current settings
            user = await self.db.get_user(user_id)
            settings = user.get('settings', {}) if user else {}
            auto_settings = settings.get('auto_boost', {})
            
            text = f"""
⚙️ <b>Auto Boost Settings</b>

<b>🎯 Current Configuration:</b>
• Default Views per Post: {auto_settings.get('default_views', 500):,}
• Boost Delay: {auto_settings.get('delay_min', 2)}-{auto_settings.get('delay_max', 8)} seconds
• Max Posts per Hour: {auto_settings.get('max_posts_per_hour', 10)}
• Detection Delay: {auto_settings.get('detection_delay', 300)} seconds

<b>🤖 Monitoring Settings:</b>
• Check Interval: {auto_settings.get('check_interval', 60)} seconds
• Account Rotation: {'Enabled' if auto_settings.get('rotate_accounts', True) else 'Disabled'}
• Smart Timing: {'Enabled' if auto_settings.get('smart_timing', True) else 'Disabled'}

<b>🔧 Advanced Options:</b>
• Retry Failed Boosts: {'Enabled' if auto_settings.get('retry_failed', True) else 'Disabled'}
• Weekend Mode: {'Enabled' if auto_settings.get('weekend_mode', False) else 'Disabled'}
• Quiet Hours: {auto_settings.get('quiet_start', '00:00')}-{auto_settings.get('quiet_end', '06:00')}
            """
            
            keyboard = self._get_settings_keyboard()
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("⚙️ Auto boost settings loaded")
            
        except Exception as e:
            logger.error(f"Error in auto settings: {e}")
            await callback.answer("❌ Failed to load settings", show_alert=True)
    
    async def _start_monitoring(self):
        """Start monitoring for new posts"""
        try:
            # Start monitoring workers
            worker_count = min(3, self.config.MAX_ACTIVE_CLIENTS // 20)
            
            for i in range(worker_count):
                worker = asyncio.create_task(self._monitoring_worker(f"monitor-{i}"))
                self._boost_workers.append(worker)
            
            logger.info(f"✅ Started {worker_count} auto boost monitoring workers")
            
        except Exception as e:
            logger.error(f"Error starting monitoring: {e}")
            raise
    
    async def _monitoring_worker(self, worker_name: str):
        """Background worker for monitoring channels"""
        logger.info(f"🔧 Started auto boost monitoring worker: {worker_name}")
        
        while self._running:
            try:
                # Get active auto campaigns
                active_campaigns = await self.db.fetch_all(
                    """
                    SELECT vbc.*, c.channel_id, c.user_id
                    FROM view_boost_campaigns vbc
                    JOIN channels c ON vbc.channel_id = c.id
                    WHERE vbc.campaign_type = 'auto' AND vbc.status = 'active'
                    AND vbc.updated_at < NOW() - INTERVAL '5 minutes'
                    LIMIT 10
                    """
                )
                
                # Process each campaign
                for campaign in active_campaigns:
                    try:
                        await self._process_auto_campaign(campaign)
                    except Exception as e:
                        logger.error(f"Error processing campaign {campaign['id']}: {e}")
                
                # Wait before next check
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring worker {worker_name}: {e}")
                await asyncio.sleep(30)  # Brief pause before continuing
    
    async def _process_auto_campaign(self, campaign: Dict[str, Any]):
        """Process individual auto campaign"""
        try:
            user_id = campaign['user_id']
            channel_id = campaign['channel_id']
            
            # Get user accounts
            accounts = await self.db.get_user_accounts(user_id, active_only=True)
            if not accounts:
                return
            
            # Check for new posts in the channel
            new_posts = await self._check_for_new_posts(channel_id, accounts[0])
            
            if new_posts:
                for post in new_posts:
                    # Create boost campaign for new post
                    await self._create_auto_boost_for_post(campaign, post)
            
            # Update campaign last check time
            await self.db.execute_query(
                "UPDATE view_boost_campaigns SET updated_at = NOW() WHERE id = $1",
                campaign['id']
            )
            
        except Exception as e:
            logger.error(f"Error processing auto campaign: {e}")
    
    async def _check_for_new_posts(self, channel_id: int, account: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check channel for new posts"""
        try:
            client = await self.bot_core.get_client(account['id'])
            if not client:
                return []
            
            # Check rate limits
            if not await self.bot_core.check_rate_limit(account['id']):
                return []
            
            # Get recent messages
            messages = await client.get_messages(channel_id, limit=5)
            
            # Update rate limiter
            await self.bot_core.increment_rate_limit(account['id'])
            
            # Filter for new posts (within last hour)
            new_posts = []
            cutoff_time = datetime.now() - timedelta(hours=1)
            
            for message in messages:
                if message.date and message.date.replace(tzinfo=None) > cutoff_time:
                    # Check if we already have a campaign for this message
                    existing = await self.db.fetch_one(
                        "SELECT id FROM view_boost_campaigns WHERE message_id = $1",
                        message.id
                    )
                    
                    if not existing:
                        new_posts.append({
                            'message_id': message.id,
                            'date': message.date,
                            'text': message.text or '',
                            'views': getattr(message, 'views', 0)
                        })
            
            return new_posts
            
        except Exception as e:
            logger.error(f"Error checking for new posts: {e}")
            return []
    
    async def _create_auto_boost_for_post(self, campaign: Dict[str, Any], post: Dict[str, Any]):
        """Create auto boost campaign for new post"""
        try:
            # Get user settings
            user = await self.db.get_user(campaign['user_id'])
            settings = user.get('settings', {}) if user else {}
            auto_settings = settings.get('auto_boost', {})
            
            # Calculate boost parameters
            target_views = auto_settings.get('default_views', 500)
            
            # Create new campaign
            new_campaign_id = await self.db.create_view_boost_campaign(
                campaign['user_id'],
                campaign['channel_id'],
                post['message_id'],
                target_views,
                'auto'
            )
            
            if new_campaign_id:
                # Start boosting process
                await self._start_boost_process(new_campaign_id)
                
                logger.info(f"Created auto boost campaign {new_campaign_id} for post {post['message_id']}")
                
        except Exception as e:
            logger.error(f"Error creating auto boost for post: {e}")
    
    async def _start_boost_process(self, campaign_id: int):
        """Start the boost process for a campaign"""
        try:
            # Create boost task
            boost_task = asyncio.create_task(self._execute_boost_campaign(campaign_id))
            
            # Store task reference (optional, for tracking)
            logger.info(f"Started boost process for campaign {campaign_id}")
            
        except Exception as e:
            logger.error(f"Error starting boost process: {e}")
    
    async def _execute_boost_campaign(self, campaign_id: int):
        """Execute boost campaign"""
        try:
            # Get campaign details
            campaign_progress = await self.universal_db.get_campaign_progress(campaign_id)
            if 'error' in campaign_progress:
                return
            
            campaign = campaign_progress['campaign']
            
            # Get user accounts
            accounts = await self.db.get_user_accounts(campaign['user_id'], active_only=True)
            if not accounts:
                await self.db.update_campaign_progress(campaign_id, 0, 'failed')
                return
            
            # Execute boost in batches
            target_views = campaign['target_views']
            current_views = campaign['current_views']
            remaining_views = target_views - current_views
            
            batch_size = min(50, remaining_views)  # Boost in batches of 50
            
            while remaining_views > 0 and campaign['status'] == 'active':
                # Select accounts for this batch
                batch_accounts = accounts[:min(len(accounts), batch_size)]
                
                # Execute boost batch
                batch_success = 0
                for account in batch_accounts:
                    try:
                        success = await self._boost_single_view(campaign, account)
                        if success:
                            batch_success += 1
                            
                        # Random delay between boosts
                        delay = self.config.VIEW_BOOST_DELAY_MIN + (
                            self.config.VIEW_BOOST_DELAY_MAX - self.config.VIEW_BOOST_DELAY_MIN
                        ) * 0.5  # Use average delay
                        await asyncio.sleep(delay)
                        
                    except Exception as e:
                        logger.error(f"Error in single boost: {e}")
                
                # Update campaign progress
                new_views = current_views + batch_success
                await self.db.update_campaign_progress(campaign_id, new_views)
                
                current_views = new_views
                remaining_views = target_views - current_views
                
                # Check if campaign is completed
                if remaining_views <= 0:
                    await self.db.update_campaign_progress(campaign_id, current_views, 'completed')
                    break
                
                # Wait before next batch
                await asyncio.sleep(30)
                
                # Refresh campaign status
                updated_campaign = await self.db.fetch_one(
                    "SELECT status FROM view_boost_campaigns WHERE id = $1",
                    campaign_id
                )
                if updated_campaign and updated_campaign['status'] != 'active':
                    break
            
        except Exception as e:
            logger.error(f"Error executing boost campaign: {e}")
            await self.db.update_campaign_progress(campaign_id, None, 'failed')
    
    async def _boost_single_view(self, campaign: Dict[str, Any], account: Dict[str, Any]) -> bool:
        """Boost single view using account"""
        try:
            client = await self.bot_core.get_client(account['id'])
            if not client:
                return False
            
            # Check rate limits
            if not await self.bot_core.check_rate_limit(account['id']):
                return False
            
            # Get channel and message
            channel_entity = await client.get_entity(campaign['channel_id'])
            
            # Use GetMessagesViewsRequest to boost views
            result = await client(functions.messages.GetMessagesViewsRequest(
                peer=channel_entity,
                id=[campaign['message_id']],
                increment=True
            ))
            
            # Update rate limiter
            await self.bot_core.increment_rate_limit(account['id'])
            
            # Log the boost
            await self.db.log_view_boost(
                campaign['id'],
                account['id'],
                1,  # One view added
                True,
                None
            )
            
            return True
            
        except Exception as e:
            # Log failed boost
            await self.db.log_view_boost(
                campaign['id'],
                account['id'],
                0,
                False,
                str(e)
            )
            logger.error(f"Error boosting single view: {e}")
            return False
    
    def _get_setup_channels_keyboard(self, channels: List[Dict[str, Any]]):
        """Get setup channels keyboard"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        buttons = []
        
        # Add channels (max 8)
        for channel in channels[:8]:
            status = "🟢" if channel['is_active'] else "🔴"
            buttons.append([
                InlineKeyboardButton(
                    text=f"{status} {channel['title'][:30]}",
                    callback_data=f"ab_enable_{channel['id']}"
                )
            ])
        
        # Control buttons
        buttons.extend([
            [InlineKeyboardButton(text="✅ Enable All", callback_data="ab_enable_all")],
            [InlineKeyboardButton(text="⚙️ Configure Settings", callback_data="ab_configure")],
            [InlineKeyboardButton(text="🔙 Back to Auto Boost", callback_data="vm_auto_boost")]
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
            [
                InlineKeyboardButton(text="⏸️ Pause All", callback_data="ab_pause_all"),
                InlineKeyboardButton(text="▶️ Resume All", callback_data="ab_resume_all")
            ],
            [InlineKeyboardButton(text="➕ Setup New", callback_data="ab_setup")],
            [InlineKeyboardButton(text="🔙 Back to Auto Boost", callback_data="vm_auto_boost")]
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_settings_keyboard(self):
        """Get settings keyboard"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        buttons = [
            [
                InlineKeyboardButton(text="🎯 Default Views", callback_data="ab_set_views"),
                InlineKeyboardButton(text="⏱️ Timing Settings", callback_data="ab_set_timing")
            ],
            [
                InlineKeyboardButton(text="📱 Account Settings", callback_data="ab_set_accounts"),
                InlineKeyboardButton(text="🔍 Detection Settings", callback_data="ab_set_detection")
            ],
            [
                InlineKeyboardButton(text="🌙 Quiet Hours", callback_data="ab_set_quiet"),
                InlineKeyboardButton(text="📊 Monitoring", callback_data="ab_set_monitoring")
            ],
            [
                InlineKeyboardButton(text="💾 Save Settings", callback_data="ab_save_settings"),
                InlineKeyboardButton(text="🔄 Reset to Default", callback_data="ab_reset_settings")
            ],
            [InlineKeyboardButton(text="🔙 Back to Auto Boost", callback_data="vm_auto_boost")]
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
    
    def _get_no_accounts_keyboard(self):
        """Get no accounts keyboard"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        buttons = [
            [InlineKeyboardButton(text="📱 Add Account", callback_data="account_management")],
            [InlineKeyboardButton(text="🔙 Back to View Manager", callback_data="view_manager")]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_no_campaigns_keyboard(self):
        """Get no campaigns keyboard"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        buttons = [
            [InlineKeyboardButton(text="⚙️ Setup Auto Boost", callback_data="ab_setup")],
            [InlineKeyboardButton(text="🔙 Back to Auto Boost", callback_data="vm_auto_boost")]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    async def shutdown(self):
        """Shutdown auto boost handler"""
        try:
            logger.info("⏹️ Shutting down auto boost handler...")
            
            self._running = False
            
            # Cancel all workers
            for worker in self._boost_workers:
                worker.cancel()
            
            # Wait for workers to finish
            if self._boost_workers:
                await asyncio.gather(*self._boost_workers, return_exceptions=True)
            
            logger.info("✅ Auto boost handler shut down")
            
        except Exception as e:
            logger.error(f"Error shutting down auto boost handler: {e}")
