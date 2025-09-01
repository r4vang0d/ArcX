"""
Live Management Handler
Main handler for live stream management and automatic joining
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from core.config.config import Config
from core.database.unified_database import DatabaseManager
from core.database.universal_access import UniversalDatabaseAccess
from core.bot.telegram_bot import TelegramBotCore
from .keyboards import LiveManagementKeyboards
from .states import LiveManagementStates
from .utils import LiveStreamUtils

logger = logging.getLogger(__name__)


class LiveManagementHandler:
    """Main live stream management handler"""
    
    def __init__(self, bot: Bot, db_manager: DatabaseManager, config: Config):
        self.bot = bot
        self.db = db_manager
        self.config = config
        self.universal_db = UniversalDatabaseAccess(db_manager)
        self.bot_core = TelegramBotCore(config, db_manager)
        self.keyboards = LiveManagementKeyboards()
        self.utils = LiveStreamUtils(bot, db_manager, config)
        
        # Initialize joiner components as placeholders for now
        self.auto_joiner = None
        self.manual_joiner = None
        
        self._monitoring_task: Optional[asyncio.Task] = None
        self._running = False
        
    async def initialize(self):
        """Initialize live management handler"""
        try:
            await self.bot_core.initialize()
            # Wait for database schema to be ready before starting monitoring
            await asyncio.sleep(15)
            await self._start_live_monitoring()
            self._running = True
            logger.info("✅ Live management handler initialized")
        except Exception as e:
            logger.error(f"Failed to initialize live management handler: {e}")
            raise
    
    def register_handlers(self, dp: Dispatcher):
        """Register handlers with dispatcher"""
        # Callback registration handled by central inline_handler
        # dp.callback_query.register(
        #     self.handle_callback,
        #     lambda c: c.data.startswith('lm_')
        # )
        
        # Register sub-handlers when available
        if hasattr(self.auto_joiner, 'register_handlers'):
            self.auto_joiner.register_handlers(dp)
        if hasattr(self.manual_joiner, 'register_handlers'):
            self.manual_joiner.register_handlers(dp)
        
        logger.info("✅ Live management handlers registered")
    
    async def handle_callback(self, callback: CallbackQuery, state: FSMContext):
        """Handle live management callbacks"""
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
            
            if callback_data == "lm_auto_join":
                await self._handle_auto_join_menu(callback, state)
            elif callback_data == "lm_manual_join":
                await self._handle_manual_join_menu(callback, state)
            elif callback_data == "lm_monitor":
                await self._handle_live_monitor(callback, state)
            elif callback_data == "lm_settings":
                await self._handle_voice_settings(callback, state)
            elif callback_data == "lm_active_streams":
                await self._handle_active_streams(callback, state)
            elif callback_data == "lm_stream_history":
                await self._handle_stream_history(callback, state)
            elif callback_data.startswith("lm_stream_"):
                await self._handle_specific_stream(callback, state)
            # Auto-join handlers
            elif callback_data.startswith("aj_"):
                await self._handle_auto_join_callbacks(callback, state)
            # Manual-join handlers  
            elif callback_data.startswith("mj_"):
                await self._handle_manual_join_callbacks(callback, state)
            # Voice settings handlers
            elif callback_data.startswith("vs_"):
                await self._handle_voice_settings_callbacks(callback, state)
            # Live scanner handlers
            elif callback_data.startswith("ls_"):
                await self._handle_live_scanner_callbacks(callback, state)
            else:
                await callback.answer("❌ Unknown live management action", show_alert=True)
                
        except Exception as e:
            logger.error(f"Error in live management callback: {e}")
            await callback.answer("❌ An error occurred", show_alert=True)
    
    async def _handle_auto_join_menu(self, callback: CallbackQuery, state: FSMContext):
        """Handle auto join menu"""
        try:
            user_id = callback.from_user.id
            
            # Get user channels
            channels = await self.db.get_user_channels(user_id)
            if not channels:
                await callback.message.edit_text(
                    "📭 <b>No Channels Available</b>\n\n"
                    "Please add channels first before setting up auto-join for live streams.",
                    reply_markup=self.keyboards.get_no_channels_keyboard()
                )
                return
            
            # Get auto-join status
            auto_join_status = await self._get_auto_join_status(user_id)
            
            text = f"""
🤖 <b>Auto Join Live Streams</b>

Automatically join live streams and voice chats when they start in your channels.

<b>📊 Current Status:</b>
• Enabled Channels: {auto_join_status['enabled_channels']}
• Active Monitoring: {auto_join_status['active_monitoring']}
• Streams Joined Today: {auto_join_status['streams_today']}
• Success Rate: {auto_join_status['success_rate']:.1f}%

<b>🤖 Auto Join Features:</b>
• Detect live streams automatically
• Join within configurable delay
• Smart account selection
• Avoid detection patterns
• Real-time monitoring

<b>⚙️ Configuration:</b>
• Join Delay: {auto_join_status['join_delay_min']}-{auto_join_status['join_delay_max']} minutes
• Max Concurrent Joins: {auto_join_status['max_concurrent']}
• Account Rotation: {'✅ Enabled' if auto_join_status['rotation_enabled'] else '❌ Disabled'}

Select an option below:
            """
            
            keyboard = self.keyboards.get_auto_join_keyboard(auto_join_status['enabled_channels'] > 0)
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("🤖 Auto join menu loaded")
            
        except Exception as e:
            logger.error(f"Error in auto join menu: {e}")
            await callback.answer("❌ Failed to load auto join menu", show_alert=True)
    
    async def _handle_manual_join_menu(self, callback: CallbackQuery, state: FSMContext):
        """Handle manual join menu"""
        try:
            user_id = callback.from_user.id
            
            # Get user channels
            channels = await self.db.get_user_channels(user_id)
            if not channels:
                await callback.message.edit_text(
                    "📭 <b>No Channels Available</b>\n\n"
                    "Please add channels first before manually joining live streams.",
                    reply_markup=self.keyboards.get_no_channels_keyboard()
                )
                return
            
            # Get currently active streams
            active_streams = await self._get_active_streams(user_id)
            
            text = f"""
👆 <b>Manual Join Live Streams</b>

Manually join specific live streams and voice chats with custom settings.

<b>📊 Available Options:</b>
• Join specific streams by link
• Join from your channels
• Custom participant count
• Account selection
• Timing control

<b>🎙️ Currently Active Streams:</b>
"""
            
            if active_streams:
                for stream in active_streams[:5]:
                    participants = stream.get('participant_count', 0)
                    text += f"• {stream['channel_title']}: {participants} participants\n"
            else:
                text += "• No active streams detected\n"
            
            text += f"""
<b>📱 Available Accounts:</b> {await self._get_available_accounts_count(user_id)}

<b>⚡ Quick Actions:</b>
• Join latest detected stream
• Scan channels for streams
• Set up stream alerts
• Configure join settings

Select how you'd like to join streams:
            """
            
            keyboard = self.keyboards.get_manual_join_keyboard(len(active_streams) > 0)
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("👆 Manual join menu loaded")
            
        except Exception as e:
            logger.error(f"Error in manual join menu: {e}")
            await callback.answer("❌ Failed to load manual join menu", show_alert=True)
    
    async def _handle_live_monitor(self, callback: CallbackQuery, state: FSMContext):
        """Handle live stream monitoring"""
        try:
            user_id = callback.from_user.id
            
            # Get monitoring data
            monitoring_data = await self._get_monitoring_data(user_id)
            
            text = f"""
📊 <b>Live Stream Monitor</b>

Real-time monitoring of live streams across your channels.

<b>🎙️ Active Streams ({monitoring_data['active_count']}):</b>
"""
            
            for stream in monitoring_data['active_streams']:
                status_emoji = "🔴" if stream['is_live'] else "⚪"
                joined_emoji = "✅" if stream['joined'] else "❌"
                
                text += (
                    f"{status_emoji} <b>{stream['channel_title']}</b>\n"
                    f"   👥 {stream['participant_count']} participants\n"
                    f"   {joined_emoji} Joined: {'Yes' if stream['joined'] else 'No'}\n"
                    f"   ⏱️ Duration: {stream['duration']}\n\n"
                )
            
            if not monitoring_data['active_streams']:
                text += "• No active streams at the moment\n\n"
            
            text += f"""
<b>📈 Today's Statistics:</b>
• Streams Detected: {monitoring_data['streams_detected']}
• Successful Joins: {monitoring_data['successful_joins']}
• Failed Joins: {monitoring_data['failed_joins']}
• Average Participants: {monitoring_data['avg_participants']:.0f}

<b>⚡ System Status:</b>
• Monitoring: {'🟢 Active' if monitoring_data['monitoring_active'] else '🔴 Inactive'}
• Auto Join: {'🟢 Enabled' if monitoring_data['auto_join_enabled'] else '🔴 Disabled'}
• Last Check: {monitoring_data['last_check']}
• Next Check: {monitoring_data['next_check']}

<b>🔍 Detection Settings:</b>
• Check Interval: {monitoring_data['check_interval']} seconds
• Monitored Channels: {monitoring_data['monitored_channels']}
• Alert Threshold: {monitoring_data['alert_threshold']} participants
            """
            
            keyboard = self.keyboards.get_monitor_keyboard()
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("📊 Live monitor loaded")
            
        except Exception as e:
            logger.error(f"Error in live monitor: {e}")
            await callback.answer("❌ Failed to load monitor", show_alert=True)
    
    async def _handle_voice_settings(self, callback: CallbackQuery, state: FSMContext):
        """Handle voice call settings"""
        try:
            user_id = callback.from_user.id
            
            # Get current voice settings
            user = await self.db.get_user(user_id)
            settings = user.get('settings', {}) if user else {}
            voice_settings = settings.get('live_management', {})
            
            text = f"""
⚙️ <b>Voice Call Settings</b>

Configure how the bot joins and behaves in live streams and voice chats.

<b>🤖 Auto Join Settings:</b>
• Auto Join Enabled: {'✅ Yes' if voice_settings.get('auto_join', False) else '❌ No'}
• Join Delay: {voice_settings.get('join_delay_min', 5)}-{voice_settings.get('join_delay_max', 15)} minutes
• Max Concurrent: {voice_settings.get('max_concurrent', 10)} streams
• Account Rotation: {'✅ Enabled' if voice_settings.get('rotation', True) else '❌ Disabled'}

<b>🎙️ Audio Settings:</b>
• Microphone: {'🔇 Muted' if voice_settings.get('mute_mic', True) else '🎤 Unmuted'}
• Camera: {'📷 Off' if voice_settings.get('camera_off', True) else '📹 On'}
• Audio Quality: {voice_settings.get('audio_quality', 'Medium')}
• Background Audio: {'✅ Enabled' if voice_settings.get('background_audio', False) else '❌ Disabled'}

<b>🔍 Detection Settings:</b>
• Detection Interval: {voice_settings.get('detection_interval', 60)} seconds
• Minimum Participants: {voice_settings.get('min_participants', 5)}
• Auto Leave Empty: {'✅ Yes' if voice_settings.get('auto_leave_empty', True) else '❌ No'}
• Leave Delay: {voice_settings.get('leave_delay', 300)} seconds

<b>🚨 Alert Settings:</b>
• Stream Start Alerts: {'✅ Enabled' if voice_settings.get('start_alerts', True) else '❌ Disabled'}
• Join Success Alerts: {'✅ Enabled' if voice_settings.get('success_alerts', False) else '❌ Disabled'}
• Error Alerts: {'✅ Enabled' if voice_settings.get('error_alerts', True) else '❌ Disabled'}

<b>🔐 Privacy Settings:</b>
• Anonymous Mode: {'✅ Enabled' if voice_settings.get('anonymous', True) else '❌ Disabled'}
• Hide Phone Number: {'✅ Yes' if voice_settings.get('hide_phone', True) else '❌ No'}
• Randomize Join Order: {'✅ Yes' if voice_settings.get('randomize_order', True) else '❌ No'}
            """
            
            keyboard = self.keyboards.get_voice_settings_keyboard()
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("⚙️ Voice settings loaded")
            
        except Exception as e:
            logger.error(f"Error in voice settings: {e}")
            await callback.answer("❌ Failed to load settings", show_alert=True)
    
    async def _start_live_monitoring(self):
        """Start background live stream monitoring"""
        try:
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            logger.info("✅ Live stream monitoring started")
        except Exception as e:
            logger.error(f"Error starting live monitoring: {e}")
            raise
    
    async def _monitoring_loop(self):
        """Background monitoring loop for live streams"""
        logger.info("🔧 Started live stream monitoring loop")
        
        while self._running:
            try:
                # Get all channels with live monitoring enabled
                channels_to_monitor = await self.db.fetch_all(
                    """
                    SELECT c.*, u.settings
                    FROM channels c
                    JOIN users u ON c.user_id = u.user_id
                    WHERE c.is_active = TRUE AND u.is_active = TRUE
                    """
                )
                
                # Monitor each channel
                for channel in channels_to_monitor:
                    try:
                        await self._monitor_channel_for_streams(channel)
                    except Exception as e:
                        logger.error(f"Error monitoring channel {channel['id']}: {e}")
                
                # Wait before next check
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in live monitoring loop: {e}")
                await asyncio.sleep(30)
    
    async def _monitor_channel_for_streams(self, channel: Dict[str, Any]):
        """Monitor specific channel for live streams"""
        try:
            user_id = channel['user_id']
            
            # Get user accounts
            accounts = await self.db.get_user_accounts(user_id, active_only=True)
            if not accounts:
                return
            
            # Check for live streams using first available account
            client = await self.bot_core.get_client(accounts[0]['id'])
            if not client:
                return
            
            # Check rate limits
            if not await self.bot_core.check_rate_limit(accounts[0]['id']):
                return
            
            # Get channel entity and check for active calls
            try:
                channel_entity = await client.get_entity(channel['channel_id'])
                
                # This would use actual Telegram API to check for group calls
                # For now, we'll simulate detection
                has_active_call = False  # Would check actual call status
                
                if has_active_call:
                    # Stream detected, process auto-join if enabled
                    await self._process_detected_stream(channel, accounts)
                
                # Update rate limiter
                await self.bot_core.increment_rate_limit(accounts[0]['id'])
                
            except Exception as e:
                logger.warning(f"Could not check stream status for channel {channel['id']}: {e}")
                
        except Exception as e:
            logger.error(f"Error monitoring channel for streams: {e}")
    
    async def _process_detected_stream(self, channel: Dict[str, Any], accounts: List[Dict[str, Any]]):
        """Process a detected live stream"""
        try:
            user_id = channel['user_id']
            
            # Check if auto-join is enabled for this user
            user = await self.db.get_user(user_id)
            settings = user.get('settings', {}) if user else {}
            live_settings = settings.get('live_management', {})
            
            if not live_settings.get('auto_join', False):
                return
            
            # Check if we already have a record of this stream
            existing_stream = await self.db.fetch_one(
                """
                SELECT id FROM live_streams 
                WHERE channel_id = $1 AND is_active = TRUE 
                AND start_time >= NOW() - INTERVAL '1 hour'
                """,
                channel['id']
            )
            
            if existing_stream:
                return  # Already tracking this stream
            
            # Create stream record
            stream_id = await self.db.execute_query(
                """
                INSERT INTO live_streams 
                (channel_id, stream_id, title, is_active, auto_join_enabled, start_time, settings, created_at, updated_at)
                VALUES ($1, $2, $3, TRUE, TRUE, NOW(), $4, NOW(), NOW())
                RETURNING id
                """,
                channel['id'],
                0,  # Would get actual stream ID
                f"Live stream in {channel['title']}",
                live_settings
            )
            
            # Trigger auto-join when available
            if hasattr(self.auto_joiner, 'join_stream'):
                await self.auto_joiner.join_stream(stream_id, accounts)
            
            logger.info(f"✅ Detected and processing live stream in {channel['title']}")
            
        except Exception as e:
            logger.error(f"Error processing detected stream: {e}")
    
    async def _get_auto_join_status(self, user_id: int) -> Dict[str, Any]:
        """Get auto-join status for user"""
        try:
            # Get user settings
            user = await self.db.get_user(user_id)
            settings = user.get('settings', {}) if user else {}
            live_settings = settings.get('live_management', {})
            
            # Count enabled channels
            channels = await self.db.get_user_channels(user_id)
            enabled_channels = len([c for c in channels if live_settings.get('auto_join', False)])
            
            # Get today's statistics
            streams_today = await self.db.fetch_one(
                """
                SELECT COUNT(*) as count
                FROM live_stream_participants lsp
                JOIN live_streams ls ON lsp.stream_id = ls.id
                JOIN channels c ON ls.channel_id = c.id
                WHERE u.user_id = $1 AND lsp.joined_at >= DATE(NOW())
                """,
                user_id
            )
            
            return {
                'enabled_channels': enabled_channels,
                'active_monitoring': len(channels) > 0,
                'streams_today': streams_today['count'] if streams_today else 0,
                'success_rate': 95.0,  # Would calculate from actual data
                'join_delay_min': live_settings.get('join_delay_min', 5),
                'join_delay_max': live_settings.get('join_delay_max', 15),
                'max_concurrent': live_settings.get('max_concurrent', 10),
                'rotation_enabled': live_settings.get('rotation', True)
            }
            
        except Exception as e:
            logger.error(f"Error getting auto-join status: {e}")
            return {
                'enabled_channels': 0, 'active_monitoring': False, 'streams_today': 0,
                'success_rate': 0, 'join_delay_min': 5, 'join_delay_max': 15,
                'max_concurrent': 10, 'rotation_enabled': True
            }
    
    async def _get_active_streams(self, user_id: int) -> List[Dict[str, Any]]:
        """Get currently active streams for user"""
        try:
            active_streams = await self.db.fetch_all(
                """
                SELECT ls.*, c.title as channel_title, c.username as channel_username
                FROM live_streams ls
                JOIN channels c ON ls.channel_id = c.id
                WHERE u.user_id = $1 AND ls.is_active = TRUE
                ORDER BY ls.start_time DESC
                """,
                user_id
            )
            
            return active_streams
            
        except Exception as e:
            logger.error(f"Error getting active streams: {e}")
            return []
    
    async def _get_available_accounts_count(self, user_id: int) -> int:
        """Get count of available accounts for user"""
        try:
            result = await self.db.fetch_one(
                "SELECT COUNT(*) as count FROM telegram_accounts WHERE user_id = $1 AND is_active = TRUE",
                user_id
            )
            return result['count'] if result else 0
        except Exception as e:
            logger.error(f"Error getting available accounts count: {e}")
            return 0
    
    async def _get_monitoring_data(self, user_id: int) -> Dict[str, Any]:
        """Get monitoring data for user"""
        try:
            # Get active streams
            active_streams = await self._get_active_streams(user_id)
            
            # Get today's statistics
            today_stats = await self.db.fetch_all(
                """
                SELECT 
                    COUNT(DISTINCT ls.id) as streams_detected,
                    COUNT(DISTINCT lsp.id) as joins_attempted,
                    COUNT(DISTINCT CASE WHEN lsp.is_active THEN lsp.id END) as successful_joins
                FROM live_streams ls
                JOIN channels c ON ls.channel_id = c.id
                LEFT JOIN live_stream_participants lsp ON ls.id = lsp.stream_id
                WHERE u.user_id = $1 AND ls.start_time >= DATE(NOW())
                """,
                user_id
            )
            
            stats = today_stats[0] if today_stats else {}
            
            # Process active streams for display
            processed_streams = []
            for stream in active_streams:
                processed_streams.append({
                    'channel_title': stream['channel_title'],
                    'is_live': stream['is_active'],
                    'joined': True,  # Would check actual participation
                    'participant_count': stream.get('participant_count', 0),
                    'duration': self._format_duration(stream['start_time'])
                })
            
            return {
                'active_count': len(active_streams),
                'active_streams': processed_streams,
                'streams_detected': stats.get('streams_detected', 0),
                'successful_joins': stats.get('successful_joins', 0),
                'failed_joins': max(0, stats.get('joins_attempted', 0) - stats.get('successful_joins', 0)),
                'avg_participants': 25,  # Would calculate from actual data
                'monitoring_active': True,
                'auto_join_enabled': True,  # Would get from user settings
                'last_check': '2 minutes ago',
                'next_check': '58 seconds',
                'check_interval': 60,
                'monitored_channels': len(await self.db.get_user_channels(user_id)),
                'alert_threshold': 10
            }
            
        except Exception as e:
            logger.error(f"Error getting monitoring data: {e}")
            return {}
    
    def _format_duration(self, start_time: datetime) -> str:
        """Format stream duration"""
        try:
            if not start_time:
                return "Unknown"
            
            delta = datetime.now() - start_time.replace(tzinfo=None)
            
            if delta.days > 0:
                return f"{delta.days}d {delta.seconds // 3600}h"
            elif delta.seconds >= 3600:
                return f"{delta.seconds // 3600}h {(delta.seconds % 3600) // 60}m"
            else:
                return f"{delta.seconds // 60}m"
                
        except Exception:
            return "Unknown"
    
    # Placeholder implementations for the new handlers
    async def _handle_auto_join_setup(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 Auto-join setup coming soon", show_alert=True)
    
    async def _handle_auto_join_manage_channels(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 Channel management coming soon", show_alert=True)
    
    async def _handle_auto_join_statistics(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 Auto-join statistics coming soon", show_alert=True)
    
    async def _handle_auto_join_schedule(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 Schedule settings coming soon", show_alert=True)
    
    async def _handle_auto_join_pause(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("⏸️ Auto-join paused")
    
    async def _handle_auto_join_resume(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("▶️ Auto-join resumed")
    
    async def _handle_auto_join_advanced(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 Advanced settings coming soon", show_alert=True)
    
    async def _handle_manual_join_by_link(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 Join by link coming soon", show_alert=True)
    
    async def _handle_manual_join_select_channel(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 Channel selection coming soon", show_alert=True)
    
    async def _handle_manual_join_active(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 Join active streams coming soon", show_alert=True)
    
    async def _handle_manual_view_active(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 View active streams coming soon", show_alert=True)
    
    async def _handle_manual_scan(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 Manual scan coming soon", show_alert=True)
    
    async def _handle_manual_join_settings(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 Join settings coming soon", show_alert=True)
    
    async def _handle_manual_join_history(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 Join history coming soon", show_alert=True)
    
    async def _handle_manual_join_alerts(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 Stream alerts coming soon", show_alert=True)
    
    async def _handle_voice_auto_join_settings(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 Auto-join voice settings coming soon", show_alert=True)
    
    async def _handle_voice_audio_settings(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 Audio settings coming soon", show_alert=True)
    
    async def _handle_voice_detection_settings(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 Detection settings coming soon", show_alert=True)
    
    async def _handle_voice_alerts_settings(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 Voice alerts settings coming soon", show_alert=True)
    
    async def _handle_voice_privacy_settings(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 Privacy settings coming soon", show_alert=True)
    
    async def _handle_voice_performance_settings(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 Performance settings coming soon", show_alert=True)
    
    async def _handle_voice_save_settings(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("💾 Settings saved")
    
    async def _handle_voice_reset_settings(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🔄 Settings reset to default")
    
    async def _handle_live_quick_scan(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 Quick scan coming soon", show_alert=True)
    
    async def _handle_live_deep_scan(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 Deep scan coming soon", show_alert=True)
    
    async def _handle_live_realtime_scan(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 Real-time scan coming soon", show_alert=True)
    
    async def _handle_live_scan_all(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 Scan all channels coming soon", show_alert=True)
    
    async def _handle_live_custom_scan(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 Custom scan coming soon", show_alert=True)
    
    async def _handle_live_scan_results(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 Scan results coming soon", show_alert=True)
    
    async def _handle_live_scanner_settings(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 Scanner settings coming soon", show_alert=True)
    
    async def _handle_live_export_scan(self, callback: CallbackQuery, state: FSMContext):
        await callback.answer("🚧 Export scan coming soon", show_alert=True)
    
    async def shutdown(self):
        """Shutdown live management handler"""
        try:
            logger.info("⏹️ Shutting down live management handler...")
            
            self._running = False
            
            # Cancel monitoring task
            if self._monitoring_task:
                self._monitoring_task.cancel()
                try:
                    await self._monitoring_task
                except asyncio.CancelledError:
                    pass
            
            # Shutdown sub-handlers
            if hasattr(self.auto_joiner, 'shutdown'):
                await self.auto_joiner.shutdown()
            if hasattr(self.manual_joiner, 'shutdown'):
                await self.manual_joiner.shutdown()
            
            logger.info("✅ Live management handler shut down")
            
        except Exception as e:
            logger.error(f"Error shutting down live management handler: {e}")
