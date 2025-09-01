"""
View Manager Handler
Main handler for view boosting operations - automatic and manual
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.config.config import Config
from core.database.unified_database import DatabaseManager
from core.database.universal_access import UniversalDatabaseAccess
from core.bot.telegram_bot import TelegramBotCore
from .states.states import ViewBoostStates
from .handlers.auto_boost import AutoBoostHandler
from .handlers.manual_boost import ManualBoostHandler
from .utils.scheduler import BoostScheduler
from .utils.time_parse import TimeParser

logger = logging.getLogger(__name__)


class ViewManagerHandler:
    """Main view management handler"""
    
    def __init__(self, bot: Bot, db_manager: DatabaseManager, config: Config):
        self.bot = bot
        self.db = db_manager
        self.config = config
        self.universal_db = UniversalDatabaseAccess(db_manager)
        self.bot_core = TelegramBotCore(config, db_manager)
        self.scheduler = BoostScheduler(db_manager, config)
        self.time_parser = TimeParser()
        
        # Sub-handlers
        self.auto_boost = AutoBoostHandler(bot, db_manager, config)
        self.manual_boost = ManualBoostHandler(bot, db_manager, config)
        
    async def initialize(self):
        """Initialize view manager handler"""
        try:
            await self.bot_core.initialize()
            await self.auto_boost.initialize()
            await self.manual_boost.initialize()
            await self.scheduler.initialize()
            logger.info("✅ View manager handler initialized")
        except Exception as e:
            logger.error(f"Failed to initialize view manager handler: {e}")
            raise
    
    def register_handlers(self, dp: Dispatcher):
        """Register handlers with dispatcher"""
        # Main view manager callbacks
        dp.callback_query.register(
            self.handle_callback,
            lambda c: c.data.startswith('vm_')
        )
        
        # FSM handlers
        dp.message.register(
            self.handle_boost_input,
            ViewBoostStates.waiting_for_boost_params
        )
        
        dp.message.register(
            self.handle_message_link,
            ViewBoostStates.waiting_for_message_link
        )
        
        # Register sub-handlers
        self.auto_boost.register_handlers(dp)
        self.manual_boost.register_handlers(dp)
        
        logger.info("✅ View manager handlers registered")
    
    async def handle_callback(self, callback: CallbackQuery, state: FSMContext):
        """Handle view manager callbacks"""
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
            if callback_data == "vm_auto_boost":
                await self._handle_auto_boost_menu(callback, state)
            elif callback_data == "vm_manual_boost":
                await self._handle_manual_boost_menu(callback, state)
            elif callback_data == "vm_schedule":
                await self._handle_schedule_menu(callback, state)
            elif callback_data == "vm_stats":
                await self._handle_stats_menu(callback, state)
            elif callback_data.startswith("vm_boost_channel_"):
                await self._handle_boost_channel(callback, state)
            elif callback_data.startswith("vm_campaign_"):
                await self._handle_campaign_action(callback, state)
            else:
                await callback.answer("❌ Unknown view manager action", show_alert=True)
                
        except Exception as e:
            logger.error(f"Error in view manager callback: {e}")
            await callback.answer("❌ An error occurred. Please try again.", show_alert=True)
    
    async def _handle_auto_boost_menu(self, callback: CallbackQuery, state: FSMContext):
        """Handle auto boost menu"""
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
            
            # Get active auto boost campaigns
            active_campaigns = await self.db.fetch_all(
                """
                SELECT vbc.*, c.title as channel_title
                FROM view_boost_campaigns vbc
                JOIN channels c ON vbc.channel_id = c.id
                WHERE vbc.user_id = $1 AND vbc.campaign_type = 'auto' AND vbc.status = 'active'
                ORDER BY vbc.created_at DESC
                """,
                user_id
            )
            
            text = f"""
🤖 <b>Auto View Boosting</b>

Automatically boost views on new posts in your channels.

📊 <b>Current Status:</b>
• Active Auto Campaigns: {len(active_campaigns)}
• Available Channels: {len(channels)}

<b>🔧 Auto Boost Features:</b>
• Automatically detect new posts
• Boost views based on your settings
• Smart timing to appear natural
• Multiple account coordination
• Real-time monitoring

Select an option below:
            """
            
            keyboard = self._get_auto_boost_keyboard(len(active_campaigns) > 0)
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("🤖 Auto boost menu loaded")
            
        except Exception as e:
            logger.error(f"Error in auto boost menu: {e}")
            await callback.answer("❌ Failed to load auto boost menu", show_alert=True)
    
    async def _handle_manual_boost_menu(self, callback: CallbackQuery, state: FSMContext):
        """Handle manual boost menu"""
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
            
            text = """
👆 <b>Manual View Boosting</b>

Boost views on specific posts with custom settings.

<b>🎯 Manual Boost Options:</b>
• Boost specific posts by link
• Custom view targets
• Immediate or scheduled execution
• Account selection
• Progress monitoring

<b>📝 How to Use:</b>
1. Select a channel or provide post link
2. Set your boost parameters
3. Choose accounts to use
4. Start the boost campaign

Select how you'd like to boost views:
            """
            
            keyboard = self._get_manual_boost_keyboard()
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("👆 Manual boost menu loaded")
            
        except Exception as e:
            logger.error(f"Error in manual boost menu: {e}")
            await callback.answer("❌ Failed to load manual boost menu", show_alert=True)
    
    async def _handle_schedule_menu(self, callback: CallbackQuery, state: FSMContext):
        """Handle schedule menu"""
        try:
            user_id = callback.from_user.id
            
            # Get scheduled campaigns
            scheduled_campaigns = await self.db.fetch_all(
                """
                SELECT vbc.*, c.title as channel_title
                FROM view_boost_campaigns vbc
                JOIN channels c ON vbc.channel_id = c.id
                WHERE vbc.user_id = $1 AND vbc.start_time > NOW()
                ORDER BY vbc.start_time ASC
                """,
                user_id
            )
            
            text = f"""
⏰ <b>Boost Scheduling</b>

Schedule view boost campaigns for optimal timing.

📊 <b>Scheduled Campaigns:</b> {len(scheduled_campaigns)}

<b>🕐 Scheduling Features:</b>
• Schedule boosts for specific times
• Repeat campaigns daily/weekly
• Peak time optimization
• Time zone support
• Automatic execution

<b>💡 Best Practices:</b>
• Schedule during peak hours for your audience
• Space out boosts to look natural
• Consider different time zones
• Monitor performance and adjust timing
            """
            
            if scheduled_campaigns:
                text += "\n\n<b>📅 Upcoming Campaigns:</b>\n"
                for campaign in scheduled_campaigns[:5]:
                    start_time = campaign['start_time'].strftime('%m/%d %H:%M')
                    text += f"• {campaign['channel_title']}: {start_time}\n"
            
            keyboard = self._get_schedule_keyboard(len(scheduled_campaigns) > 0)
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("⏰ Schedule menu loaded")
            
        except Exception as e:
            logger.error(f"Error in schedule menu: {e}")
            await callback.answer("❌ Failed to load schedule menu", show_alert=True)
    
    async def _handle_stats_menu(self, callback: CallbackQuery, state: FSMContext):
        """Handle stats menu"""
        try:
            user_id = callback.from_user.id
            
            # Get boost statistics
            stats = await self._get_boost_statistics(user_id)
            
            text = f"""
📊 <b>View Boost Statistics</b>

<b>📈 Campaign Overview:</b>
• Total Campaigns: {stats['total_campaigns']}
• Active Campaigns: {stats['active_campaigns']}
• Completed Campaigns: {stats['completed_campaigns']}
• Success Rate: {stats['success_rate']:.1f}%

<b>👁️ View Statistics:</b>
• Total Views Boosted: {stats['total_views']:,}
• Views This Month: {stats['monthly_views']:,}
• Views Today: {stats['daily_views']:,}
• Average per Campaign: {stats['avg_views_per_campaign']:,.0f}

<b>📱 Account Usage:</b>
• Active Accounts: {stats['active_accounts']}
• Total Boost Actions: {stats['total_actions']:,}
• Success Rate: {stats['action_success_rate']:.1f}%

<b>🏆 Top Performing:</b>
• Best Channel: {stats['top_channel']}
• Highest Single Boost: {stats['highest_boost']:,} views
            """
            
            keyboard = self._get_stats_keyboard()
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("📊 Statistics loaded")
            
        except Exception as e:
            logger.error(f"Error in stats menu: {e}")
            await callback.answer("❌ Failed to load statistics", show_alert=True)
    
    async def _handle_boost_channel(self, callback: CallbackQuery, state: FSMContext):
        """Handle boost specific channel"""
        try:
            # Extract channel ID
            channel_id = int(callback.data.split("_")[-1])
            
            # Get channel info
            channel = await self.db.get_channel_by_id(channel_id)
            if not channel:
                await callback.answer("❌ Channel not found", show_alert=True)
                return
            
            text = f"""
🚀 <b>Boost Views - {channel['title']}</b>

Choose how you'd like to boost views for this channel:

<b>📋 Channel Info:</b>
• Members: {channel.get('member_count', 'Unknown'):,}
• Status: {'Active' if channel['is_active'] else 'Inactive'}

<b>🎯 Boost Options:</b>
• Quick Boost - Boost latest post
• Custom Boost - Choose specific post
• Auto Setup - Enable automatic boosting
• Schedule Boost - Set up timed boosting

Select your preferred boost method:
            """
            
            keyboard = self._get_channel_boost_keyboard(channel_id)
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer(f"🚀 Boost options for {channel['title']}")
            
        except Exception as e:
            logger.error(f"Error in boost channel: {e}")
            await callback.answer("❌ Failed to load boost options", show_alert=True)
    
    async def _handle_campaign_action(self, callback: CallbackQuery, state: FSMContext):
        """Handle campaign-specific actions"""
        try:
            # Extract campaign ID and action
            parts = callback.data.split("_")
            campaign_id = int(parts[-1])
            action = parts[-2] if len(parts) > 2 else "view"
            
            if action == "view":
                await self._show_campaign_details(callback, campaign_id)
            elif action == "pause":
                await self._pause_campaign(callback, campaign_id)
            elif action == "resume":
                await self._resume_campaign(callback, campaign_id)
            elif action == "stop":
                await self._stop_campaign(callback, campaign_id)
            else:
                await callback.answer("❌ Unknown campaign action", show_alert=True)
                
        except Exception as e:
            logger.error(f"Error in campaign action: {e}")
            await callback.answer("❌ Failed to process campaign action", show_alert=True)
    
    async def _show_campaign_details(self, callback: CallbackQuery, campaign_id: int):
        """Show detailed campaign information"""
        try:
            # Get campaign progress
            progress = await self.universal_db.get_campaign_progress(campaign_id)
            
            if 'error' in progress:
                await callback.answer("❌ Campaign not found", show_alert=True)
                return
            
            campaign = progress['campaign']
            stats = progress['statistics']
            
            text = f"""
📊 <b>Campaign Details</b>

<b>📋 Campaign Info:</b>
• Channel: {campaign['channel_title']}
• Message ID: {campaign['message_id']}
• Type: {campaign['campaign_type'].title()}
• Status: {campaign['status'].title()}

<b>🎯 Progress:</b>
• Target Views: {campaign['target_views']:,}
• Current Views: {campaign['current_views']:,}
• Progress: {stats['progress_percentage']:.1f}%
• Remaining: {stats['remaining_views']:,}

<b>📈 Performance:</b>
• Total Attempts: {stats['total_attempts']}
• Successful: {stats['successful_attempts']}
• Success Rate: {stats['success_rate']:.1f}%

<b>📅 Timeline:</b>
• Created: {campaign['created_at'].strftime('%Y-%m-%d %H:%M')}
• Updated: {campaign['updated_at'].strftime('%Y-%m-%d %H:%M')}
            """
            
            keyboard = self._get_campaign_details_keyboard(campaign_id, campaign['status'])
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("📊 Campaign details loaded")
            
        except Exception as e:
            logger.error(f"Error showing campaign details: {e}")
            await callback.answer("❌ Failed to load campaign details", show_alert=True)
    
    async def handle_boost_input(self, message: Message, state: FSMContext):
        """Handle boost parameter input"""
        try:
            user_data = await state.get_data()
            boost_params = message.text.strip()
            
            # Parse boost parameters
            parsed_params = await self._parse_boost_params(boost_params)
            
            if not parsed_params['valid']:
                await message.answer(
                    f"❌ <b>Invalid Parameters</b>\n\n"
                    f"Error: {parsed_params['error']}\n\n"
                    f"Please use format: <code>views=1000 delay=5-10</code>",
                    reply_markup=self._get_retry_input_keyboard()
                )
                return
            
            # Store parameters and proceed
            await state.update_data(boost_params=parsed_params)
            
            await message.answer(
                f"✅ <b>Parameters Set</b>\n\n"
                f"• Views: {parsed_params['views']:,}\n"
                f"• Delay: {parsed_params['delay_min']}-{parsed_params['delay_max']} seconds\n"
                f"• Accounts: {parsed_params.get('accounts', 'All available')}\n\n"
                f"Proceed with the boost campaign?",
                reply_markup=self._get_confirm_boost_keyboard()
            )
            
        except Exception as e:
            logger.error(f"Error handling boost input: {e}")
            await message.answer("❌ Failed to process parameters. Please try again.")
            await state.clear()
    
    async def handle_message_link(self, message: Message, state: FSMContext):
        """Handle message link input"""
        try:
            link = message.text.strip()
            
            # Parse message link
            parsed_link = await self._parse_message_link(link)
            
            if not parsed_link['valid']:
                await message.answer(
                    f"❌ <b>Invalid Message Link</b>\n\n"
                    f"Error: {parsed_link['error']}\n\n"
                    f"Please provide a valid Telegram message link.",
                    reply_markup=self._get_retry_link_keyboard()
                )
                return
            
            # Store link data
            await state.update_data(message_link=parsed_link)
            
            await message.answer(
                f"✅ <b>Message Link Parsed</b>\n\n"
                f"• Channel: {parsed_link['channel_name']}\n"
                f"• Message ID: {parsed_link['message_id']}\n\n"
                f"Now please set your boost parameters:\n"
                f"Format: <code>views=1000 delay=5-10</code>",
                reply_markup=None
            )
            
            # Transition to boost params state
            await state.set_state(ViewBoostStates.waiting_for_boost_params)
            
        except Exception as e:
            logger.error(f"Error handling message link: {e}")
            await message.answer("❌ Failed to process message link. Please try again.")
            await state.clear()
    
    async def _parse_boost_params(self, params_text: str) -> Dict[str, Any]:
        """Parse boost parameters from text"""
        try:
            params = {}
            
            # Split by spaces and parse key=value pairs
            for param in params_text.split():
                if '=' in param:
                    key, value = param.split('=', 1)
                    params[key.lower()] = value
            
            # Validate required parameters
            if 'views' not in params:
                return {'valid': False, 'error': 'Views parameter is required'}
            
            try:
                views = int(params['views'])
                if views <= 0 or views > 100000:
                    return {'valid': False, 'error': 'Views must be between 1 and 100,000'}
            except ValueError:
                return {'valid': False, 'error': 'Views must be a number'}
            
            # Parse delay
            delay_min, delay_max = 2, 8  # defaults
            if 'delay' in params:
                delay_str = params['delay']
                if '-' in delay_str:
                    try:
                        delay_parts = delay_str.split('-')
                        delay_min = int(delay_parts[0])
                        delay_max = int(delay_parts[1])
                    except:
                        return {'valid': False, 'error': 'Invalid delay format. Use: delay=5-10'}
                else:
                    try:
                        delay_min = delay_max = int(delay_str)
                    except:
                        return {'valid': False, 'error': 'Invalid delay value'}
            
            return {
                'valid': True,
                'views': views,
                'delay_min': delay_min,
                'delay_max': delay_max,
                'accounts': params.get('accounts', 'all')
            }
            
        except Exception as e:
            return {'valid': False, 'error': f'Failed to parse parameters: {str(e)}'}
    
    async def _parse_message_link(self, link: str) -> Dict[str, Any]:
        """Parse Telegram message link"""
        try:
            import re
            
            # Match Telegram message link patterns
            patterns = [
                r'https?://t\.me/(\w+)/(\d+)',
                r'https?://telegram\.me/(\w+)/(\d+)',
                r'@(\w+)/(\d+)',
                r'(\w+)/(\d+)'
            ]
            
            for pattern in patterns:
                match = re.match(pattern, link)
                if match:
                    channel_name = match.group(1)
                    message_id = int(match.group(2))
                    
                    return {
                        'valid': True,
                        'channel_name': channel_name,
                        'message_id': message_id,
                        'original_link': link
                    }
            
            return {
                'valid': False,
                'error': 'Invalid message link format. Use: https://t.me/channel/123 or @channel/123'
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': f'Failed to parse link: {str(e)}'
            }
    
    async def _get_boost_statistics(self, user_id: int) -> Dict[str, Any]:
        """Get comprehensive boost statistics"""
        try:
            # Get campaign statistics
            campaigns = await self.db.get_user_campaigns(user_id)
            total_campaigns = len(campaigns)
            active_campaigns = len([c for c in campaigns if c['status'] == 'active'])
            completed_campaigns = len([c for c in campaigns if c['status'] == 'completed'])
            
            success_rate = (completed_campaigns / total_campaigns * 100) if total_campaigns > 0 else 0
            
            # Get view statistics
            total_views = sum(c['current_views'] for c in campaigns)
            
            # Get monthly and daily views
            monthly_views = await self.db.fetch_one(
                """
                SELECT COALESCE(SUM(current_views), 0) as views
                FROM view_boost_campaigns
                WHERE user_id = $1 AND created_at >= NOW() - INTERVAL '30 days'
                """,
                user_id
            )
            
            daily_views = await self.db.fetch_one(
                """
                SELECT COALESCE(SUM(current_views), 0) as views  
                FROM view_boost_campaigns
                WHERE user_id = $1 AND created_at >= NOW() - INTERVAL '1 day'
                """,
                user_id
            )
            
            # Get account statistics
            user_accounts = await self.db.get_user_accounts(user_id, active_only=True)
            
            # Get boost action statistics
            boost_actions = await self.db.fetch_all(
                """
                SELECT success, COUNT(*) as count
                FROM view_boost_logs vbl
                JOIN view_boost_campaigns vbc ON vbl.campaign_id = vbc.id
                WHERE vbc.user_id = $1
                GROUP BY success
                """,
                user_id
            )
            
            total_actions = sum(a['count'] for a in boost_actions)
            successful_actions = sum(a['count'] for a in boost_actions if a['success'])
            action_success_rate = (successful_actions / total_actions * 100) if total_actions > 0 else 0
            
            # Get top performing channel
            top_channel_result = await self.db.fetch_one(
                """
                SELECT c.title, SUM(vbc.current_views) as total_views
                FROM view_boost_campaigns vbc
                JOIN channels c ON vbc.channel_id = c.id
                WHERE vbc.user_id = $1
                GROUP BY c.id, c.title
                ORDER BY total_views DESC
                LIMIT 1
                """,
                user_id
            )
            
            # Get highest single boost
            highest_boost_result = await self.db.fetch_one(
                """
                SELECT MAX(current_views) as highest
                FROM view_boost_campaigns
                WHERE user_id = $1
                """,
                user_id
            )
            
            return {
                'total_campaigns': total_campaigns,
                'active_campaigns': active_campaigns,
                'completed_campaigns': completed_campaigns,
                'success_rate': success_rate,
                'total_views': total_views,
                'monthly_views': monthly_views['views'] if monthly_views else 0,
                'daily_views': daily_views['views'] if daily_views else 0,
                'avg_views_per_campaign': total_views / total_campaigns if total_campaigns > 0 else 0,
                'active_accounts': len(user_accounts),
                'total_actions': total_actions,
                'action_success_rate': action_success_rate,
                'top_channel': top_channel_result['title'] if top_channel_result else 'None',
                'highest_boost': highest_boost_result['highest'] if highest_boost_result else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting boost statistics: {e}")
            return {
                'total_campaigns': 0, 'active_campaigns': 0, 'completed_campaigns': 0,
                'success_rate': 0, 'total_views': 0, 'monthly_views': 0, 'daily_views': 0,
                'avg_views_per_campaign': 0, 'active_accounts': 0, 'total_actions': 0,
                'action_success_rate': 0, 'top_channel': 'None', 'highest_boost': 0
            }
    
    def _get_auto_boost_keyboard(self, has_active: bool) -> InlineKeyboardMarkup:
        """Get auto boost keyboard"""
        buttons = [
            [InlineKeyboardButton(text="⚙️ Setup Auto Boost", callback_data="ab_setup")],
            [InlineKeyboardButton(text="📋 View Auto Campaigns", callback_data="ab_campaigns")]
        ]
        
        if has_active:
            buttons.append([
                InlineKeyboardButton(text="⏸️ Pause All", callback_data="ab_pause_all"),
                InlineKeyboardButton(text="▶️ Resume All", callback_data="ab_resume_all")
            ])
        
        buttons.extend([
            [InlineKeyboardButton(text="⚙️ Auto Settings", callback_data="ab_settings")],
            [InlineKeyboardButton(text="🔙 Back to View Manager", callback_data="view_manager")]
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_manual_boost_keyboard(self) -> InlineKeyboardMarkup:
        """Get manual boost keyboard"""
        buttons = [
            [InlineKeyboardButton(text="🔗 Boost by Link", callback_data="mb_by_link")],
            [InlineKeyboardButton(text="📋 Select Channel", callback_data="mb_select_channel")],
            [InlineKeyboardButton(text="🚀 Quick Boost", callback_data="mb_quick_boost")],
            [InlineKeyboardButton(text="📊 Active Campaigns", callback_data="mb_campaigns")],
            [InlineKeyboardButton(text="🔙 Back to View Manager", callback_data="view_manager")]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_schedule_keyboard(self, has_scheduled: bool) -> InlineKeyboardMarkup:
        """Get schedule keyboard"""
        buttons = [
            [InlineKeyboardButton(text="➕ Schedule New", callback_data="sch_new")],
            [InlineKeyboardButton(text="📅 View Schedule", callback_data="sch_view")]
        ]
        
        if has_scheduled:
            buttons.append([
                InlineKeyboardButton(text="✏️ Edit Schedule", callback_data="sch_edit"),
                InlineKeyboardButton(text="🗑️ Clear Schedule", callback_data="sch_clear")
            ])
        
        buttons.extend([
            [InlineKeyboardButton(text="⚙️ Schedule Settings", callback_data="sch_settings")],
            [InlineKeyboardButton(text="🔙 Back to View Manager", callback_data="view_manager")]
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_stats_keyboard(self) -> InlineKeyboardMarkup:
        """Get stats keyboard"""
        buttons = [
            [
                InlineKeyboardButton(text="📈 Detailed Analytics", callback_data="st_detailed"),
                InlineKeyboardButton(text="📊 Channel Stats", callback_data="st_channels")
            ],
            [
                InlineKeyboardButton(text="📱 Account Performance", callback_data="st_accounts"),
                InlineKeyboardButton(text="📋 Export Report", callback_data="st_export")
            ],
            [
                InlineKeyboardButton(text="🔄 Refresh Stats", callback_data="vm_stats"),
                InlineKeyboardButton(text="🔙 Back to View Manager", callback_data="view_manager")
            ]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_channel_boost_keyboard(self, channel_id: int) -> InlineKeyboardMarkup:
        """Get channel boost keyboard"""
        buttons = [
            [InlineKeyboardButton(text="⚡ Quick Boost", callback_data=f"cb_quick_{channel_id}")],
            [InlineKeyboardButton(text="🎯 Custom Boost", callback_data=f"cb_custom_{channel_id}")],
            [InlineKeyboardButton(text="🤖 Enable Auto", callback_data=f"cb_auto_{channel_id}")],
            [InlineKeyboardButton(text="⏰ Schedule Boost", callback_data=f"cb_schedule_{channel_id}")],
            [InlineKeyboardButton(text="📊 Boost History", callback_data=f"cb_history_{channel_id}")],
            [InlineKeyboardButton(text="🔙 Back to Channel", callback_data=f"cm_channel_{channel_id}")]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_campaign_details_keyboard(self, campaign_id: int, status: str) -> InlineKeyboardMarkup:
        """Get campaign details keyboard"""
        buttons = []
        
        if status == 'active':
            buttons.append([
                InlineKeyboardButton(text="⏸️ Pause", callback_data=f"vm_campaign_pause_{campaign_id}"),
                InlineKeyboardButton(text="⏹️ Stop", callback_data=f"vm_campaign_stop_{campaign_id}")
            ])
        elif status == 'paused':
            buttons.append([
                InlineKeyboardButton(text="▶️ Resume", callback_data=f"vm_campaign_resume_{campaign_id}"),
                InlineKeyboardButton(text="⏹️ Stop", callback_data=f"vm_campaign_stop_{campaign_id}")
            ])
        
        buttons.extend([
            [InlineKeyboardButton(text="📊 View Logs", callback_data=f"vm_campaign_logs_{campaign_id}")],
            [InlineKeyboardButton(text="🔄 Refresh", callback_data=f"vm_campaign_view_{campaign_id}")],
            [InlineKeyboardButton(text="🔙 Back to Stats", callback_data="vm_stats")]
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_no_channels_keyboard(self) -> InlineKeyboardMarkup:
        """Get no channels keyboard"""
        buttons = [
            [InlineKeyboardButton(text="➕ Add Channel", callback_data="channel_management")],
            [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="refresh_main")]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_retry_input_keyboard(self) -> InlineKeyboardMarkup:
        """Get retry input keyboard"""
        buttons = [
            [InlineKeyboardButton(text="❓ Help Format", callback_data="mb_help_format")],
            [InlineKeyboardButton(text="🔙 Back to Manual Boost", callback_data="vm_manual_boost")]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_confirm_boost_keyboard(self) -> InlineKeyboardMarkup:
        """Get confirm boost keyboard"""
        buttons = [
            [
                InlineKeyboardButton(text="✅ Start Boost", callback_data="mb_confirm_start"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="vm_manual_boost")
            ]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_retry_link_keyboard(self) -> InlineKeyboardMarkup:
        """Get retry link keyboard"""
        buttons = [
            [InlineKeyboardButton(text="❓ Link Help", callback_data="mb_help_link")],
            [InlineKeyboardButton(text="🔙 Back to Manual Boost", callback_data="vm_manual_boost")]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    async def _pause_campaign(self, callback: CallbackQuery, campaign_id: int):
        """Pause a campaign"""
        try:
            success = await self.db.update_campaign_progress(campaign_id, None, 'paused')
            
            if success:
                await callback.answer("⏸️ Campaign paused successfully")
                await self._show_campaign_details(callback, campaign_id)
            else:
                await callback.answer("❌ Failed to pause campaign", show_alert=True)
                
        except Exception as e:
            logger.error(f"Error pausing campaign: {e}")
            await callback.answer("❌ Error pausing campaign", show_alert=True)
    
    async def _resume_campaign(self, callback: CallbackQuery, campaign_id: int):
        """Resume a campaign"""
        try:
            success = await self.db.update_campaign_progress(campaign_id, None, 'active')
            
            if success:
                await callback.answer("▶️ Campaign resumed successfully")
                await self._show_campaign_details(callback, campaign_id)
            else:
                await callback.answer("❌ Failed to resume campaign", show_alert=True)
                
        except Exception as e:
            logger.error(f"Error resuming campaign: {e}")
            await callback.answer("❌ Error resuming campaign", show_alert=True)
    
    async def _stop_campaign(self, callback: CallbackQuery, campaign_id: int):
        """Stop a campaign"""
        try:
            success = await self.db.update_campaign_progress(campaign_id, None, 'stopped')
            
            if success:
                await callback.answer("⏹️ Campaign stopped successfully")
                await self._show_campaign_details(callback, campaign_id)
            else:
                await callback.answer("❌ Failed to stop campaign", show_alert=True)
                
        except Exception as e:
            logger.error(f"Error stopping campaign: {e}")
            await callback.answer("❌ Error stopping campaign", show_alert=True)
    
    async def shutdown(self):
        """Shutdown view manager handler"""
        try:
            if hasattr(self.auto_boost, 'shutdown'):
                await self.auto_boost.shutdown()
            if hasattr(self.manual_boost, 'shutdown'):
                await self.manual_boost.shutdown()
            if hasattr(self.scheduler, 'shutdown'):
                await self.scheduler.shutdown()
            
            logger.info("✅ View manager handler shut down")
        except Exception as e:
            logger.error(f"Error shutting down view manager handler: {e}")
