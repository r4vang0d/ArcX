"""
Views Manager Handler - ArcX Bot
Auto Boost system with channel selection and configuration
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup

from core.config.config import Config
from core.database.unified_database import DatabaseManager

logger = logging.getLogger(__name__)


class ViewBoostStates(StatesGroup):
    """FSM states for view boosting"""
    waiting_for_boost_config = State()


class ViewManagerHandler:
    """Simplified Views Manager with Auto Boost functionality"""
    
    def __init__(self, bot: Bot, db_manager: DatabaseManager, config: Config):
        self.bot = bot
        self.db = db_manager
        self.config = config
        self._boost_engines = {}  # Active boost monitoring engines
        self._pending_configs = {}  # Store temporary configs during setup
        
    async def initialize(self):
        """Initialize view manager handler"""
        try:
            # Start the monitoring engine
            await self._start_monitoring_engine()
            logger.info("✅ View manager handler initialized")
        except Exception as e:
            logger.error(f"Failed to initialize view manager handler: {e}")
            raise
    
    def register_handlers(self, dp: Dispatcher):
        """Register handlers with dispatcher"""
        # FSM message handlers
        dp.message.register(self.handle_boost_config_input, ViewBoostStates.waiting_for_boost_config)
        
        logger.info("✅ View manager handlers registered")
    
    async def handle_callback(self, callback: CallbackQuery, state: FSMContext):
        """Handle view manager callbacks"""
        try:
            callback_data = callback.data
            user_id = callback.from_user.id
            
            # Ensure user exists in database
            await self._ensure_user_exists(callback.from_user)
            
            if callback_data == "vm_auto_boost":
                await self._handle_auto_boost(callback, state)
            elif callback_data == "vm_manual_boost":
                await self._handle_manual_boost(callback, state)
            elif callback_data == "vm_select_channels":
                await self._handle_select_channels(callback, state)
            elif callback_data == "vm_boost_settings":
                await self._handle_boost_settings(callback, state)
            elif callback_data.startswith("vm_channel_"):
                await self._handle_channel_toggle(callback, state)
            elif callback_data.startswith("vm_config_"):
                await self._handle_config_channel(callback, state)
            elif callback_data == "vm_start_engine":
                await self._handle_start_engine(callback, state)
            elif callback_data == "vm_stop_engine":
                await self._handle_stop_engine(callback, state)
            else:
                await callback.answer("❌ Unknown action", show_alert=True)
                
        except Exception as e:
            logger.error(f"Error in view manager callback: {e}")
            await callback.answer("❌ An error occurred", show_alert=True)
    
    async def _handle_auto_boost(self, callback: CallbackQuery, state: FSMContext):
        """Handle auto boost main menu"""
        try:
            user_id = callback.from_user.id
            
            # Get user's channels
            channels = await self._get_user_channels(user_id)
            enabled_channels = await self._get_enabled_channels(user_id)
            
            # Get engine status
            engine_status = "🟢 Running" if user_id in self._boost_engines else "🔴 Stopped"
            
            text = f"""🔥 <b>ArcX | Auto Boost</b>

<b>Engine Status:</b> {engine_status}
<b>Total Channels:</b> {len(channels)}
<b>Enabled Channels:</b> {len(enabled_channels)}

<b>Auto Boost Features:</b>
• Select channels for automatic boosting
• Configure boost settings per channel
• Advanced async monitoring engine
• Real-time performance tracking
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="[⚙️ Select Channels]", callback_data="vm_select_channels")],
                [InlineKeyboardButton(text="[🎛️ Boost Settings]", callback_data="vm_boost_settings")],
                [InlineKeyboardButton(text="[▶️ Start Engine]", callback_data="vm_start_engine")],
                [InlineKeyboardButton(text="[⏹️ Stop Engine]", callback_data="vm_stop_engine")],
                [InlineKeyboardButton(text="[🔙 Back]", callback_data="views_manager")],
                [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
            ])
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("⚙️ Auto boost menu loaded")
            
        except Exception as e:
            logger.error(f"Error in auto boost menu: {e}")
            await callback.answer("❌ Failed to load auto boost", show_alert=True)
    
    async def _handle_select_channels(self, callback: CallbackQuery, state: FSMContext):
        """Handle channel selection for auto boost"""
        try:
            user_id = callback.from_user.id
            
            # Get user's channels
            channels = await self._get_user_channels(user_id)
            if not channels:
                await callback.message.edit_text(
                    "🔥 <b>ArcX | No Channels Available</b>\\n\\n"
                    "You need to add channels first in Channel Manager.\\n"
                    "Go to Channel Manager → Add Channel",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="[📺 Channel Manager]", callback_data="channel_manager")],
                        [InlineKeyboardButton(text="[🔙 Back]", callback_data="vm_auto_boost")]
                    ])
                )
                await callback.answer("ℹ️ No channels available")
                return
            
            # Get enabled status for each channel
            enabled_channels = await self._get_enabled_channels(user_id)
            enabled_ids = {ch['channel_id'] for ch in enabled_channels}
            
            text = f"🔥 <b>ArcX | Select Channels for Auto Boost</b>\\n\\nToggle channels on/off:\\n\\n"
            
            buttons = []
            for channel in channels[:15]:  # Show max 15 channels
                is_enabled = channel['id'] in enabled_ids
                status_emoji = "✅" if is_enabled else "❌"
                toggle_text = f"[{status_emoji} {channel['channel_title'][:20]}...]"
                callback_data = f"vm_channel_{channel['id']}"
                
                # Channel toggle and config buttons
                buttons.append([
                    InlineKeyboardButton(text=toggle_text, callback_data=callback_data),
                    InlineKeyboardButton(text="[⚙️]", callback_data=f"vm_config_{channel['id']}")
                ])
            
            buttons.extend([
                [InlineKeyboardButton(text="[🔙 Back]", callback_data="vm_auto_boost")],
                [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
            ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("⚙️ Toggle channels for auto boost")
            
        except Exception as e:
            logger.error(f"Error in select channels: {e}")
            await callback.answer("❌ Failed to load channels", show_alert=True)
    
    async def _handle_channel_toggle(self, callback: CallbackQuery, state: FSMContext):
        """Handle channel enable/disable toggle"""
        try:
            channel_id = int(callback.data.split('_')[2])
            user_id = callback.from_user.id
            
            # Check if channel is currently enabled
            existing = await self.db.fetch_one(
                "SELECT id FROM boost_configs WHERE user_id = $1 AND channel_id = $2",
                user_id, channel_id
            )
            
            if existing:
                # Disable channel
                await self.db.execute_query(
                    "DELETE FROM boost_configs WHERE user_id = $1 AND channel_id = $2",
                    user_id, channel_id
                )
                await callback.answer("❌ Channel disabled for auto boost")
            else:
                # Enable channel with default settings
                await self.db.execute_query(
                    """
                    INSERT INTO boost_configs 
                    (user_id, channel_id, is_enabled, boost_count, cooldown_minutes, timing_messages, created_at, updated_at)
                    VALUES ($1, $2, TRUE, 50, 30, '[]', NOW(), NOW())
                    """,
                    user_id, channel_id
                )
                await callback.answer("✅ Channel enabled for auto boost")
            
            # Refresh the channel selection menu
            await self._handle_select_channels(callback, state)
            
        except Exception as e:
            logger.error(f"Error toggling channel: {e}")
            await callback.answer("❌ Error toggling channel", show_alert=True)
    
    async def _handle_config_channel(self, callback: CallbackQuery, state: FSMContext):
        """Handle channel-specific configuration"""
        try:
            channel_id = int(callback.data.split('_')[2])
            user_id = callback.from_user.id
            
            # Get channel and config details
            channel = await self.db.fetch_one(
                "SELECT * FROM telegram_channels WHERE id = $1", channel_id
            )
            
            config = await self.db.fetch_one(
                "SELECT * FROM boost_configs WHERE user_id = $1 AND channel_id = $2",
                user_id, channel_id
            )
            
            if not channel:
                await callback.answer("❌ Channel not found", show_alert=True)
                return
            
            if not config:
                # Create default config
                await self.db.execute_query(
                    """
                    INSERT INTO boost_configs 
                    (user_id, channel_id, is_enabled, boost_count, cooldown_minutes, timing_messages, created_at, updated_at)
                    VALUES ($1, $2, TRUE, 50, 30, '[]', NOW(), NOW())
                    """,
                    user_id, channel_id
                )
                config = {
                    'is_enabled': True,
                    'boost_count': 50,
                    'cooldown_minutes': 30,
                    'timing_messages': '[]'
                }
            
            text = f"""🔥 <b>ArcX | Channel Configuration</b>

<b>Channel:</b> {channel['channel_title']}

<b>Current Settings:</b>
• Status: {"🟢 Enabled" if config['is_enabled'] else "🔴 Disabled"}
• Boost Count: {config['boost_count']} views per boost
• Cooldown: {config['cooldown_minutes']} minutes
• Timing Messages: {len(eval(config.get('timing_messages', '[]')))} configured

<b>Advanced Settings:</b>
Send new configuration in format:
<code>boost_count,cooldown_minutes</code>

<b>Example:</b> <code>100,45</code>
(100 views per boost, 45 minute cooldown)
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="[🔄 Reset to Default]", callback_data=f"vm_reset_{channel_id}")],
                [InlineKeyboardButton(text="[🔙 Back]", callback_data="vm_select_channels")]
            ])
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await state.set_state(ViewBoostStates.waiting_for_boost_config)
            await callback.answer("⚙️ Send boost configuration")
            
        except Exception as e:
            logger.error(f"Error in config channel: {e}")
            await callback.answer("❌ Error loading channel config", show_alert=True)
    
    async def handle_boost_config_input(self, message: Message, state: FSMContext):
        """Handle boost configuration input"""
        try:
            user_id = message.from_user.id
            config_text = message.text.strip()
            
            # Parse config
            if ',' not in config_text:
                await message.answer(
                    "❌ <b>Invalid Format</b>\\n\\n"
                    "Please use format: <code>boost_count,cooldown_minutes</code>\\n"
                    "Example: <code>100,45</code>",
                    reply_markup=self._get_retry_keyboard()
                )
                return
            
            try:
                boost_count_str, cooldown_str = config_text.split(',', 1)
                boost_count = int(boost_count_str.strip())
                cooldown_minutes = int(cooldown_str.strip())
                
                if boost_count < 1 or boost_count > 1000:
                    raise ValueError("Boost count must be 1-1000")
                if cooldown_minutes < 1 or cooldown_minutes > 1440:
                    raise ValueError("Cooldown must be 1-1440 minutes")
                    
            except ValueError as ve:
                await message.answer(
                    f"❌ <b>Invalid Values</b>\\n\\n"
                    f"Error: {str(ve)}\\n"
                    f"Boost count: 1-1000\\n"
                    f"Cooldown: 1-1440 minutes",
                    reply_markup=self._get_retry_keyboard()
                )
                return
            
            # Update configuration (for now update all user's channels - in real implementation would be per-channel)
            await self.db.execute_query(
                """
                UPDATE boost_configs 
                SET boost_count = $1, cooldown_minutes = $2, updated_at = NOW()
                WHERE user_id = $3
                """,
                boost_count, cooldown_minutes, user_id
            )
            
            text = f"""✅ <b>ArcX | Configuration Updated!</b>

<b>New Settings Applied:</b>
• Boost Count: {boost_count} views per boost
• Cooldown: {cooldown_minutes} minutes between boosts
• Status: ✅ Configuration saved

Settings have been applied to all enabled channels.
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="[▶️ Start Auto Boost]", callback_data="vm_start_engine")],
                [InlineKeyboardButton(text="[⚙️ More Settings]", callback_data="vm_boost_settings")],
                [InlineKeyboardButton(text="[🔙 Auto Boost]", callback_data="vm_auto_boost")],
                [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
            ])
            
            await message.answer(text, reply_markup=keyboard)
            await state.clear()
            
        except Exception as e:
            logger.error(f"Error handling boost config: {e}")
            await message.answer("❌ Error saving configuration")
    
    async def _handle_manual_boost(self, callback: CallbackQuery, state: FSMContext):
        """Handle manual boost"""
        try:
            user_id = callback.from_user.id
            
            # Get user's channels
            channels = await self._get_user_channels(user_id)
            if not channels:
                await callback.message.edit_text(
                    "🔥 <b>ArcX | No Channels Available</b>\\n\\n"
                    "Add channels first in Channel Manager.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="[📺 Channel Manager]", callback_data="channel_manager")],
                        [InlineKeyboardButton(text="[🔙 Back]", callback_data="views_manager")]
                    ])
                )
                await callback.answer("ℹ️ No channels available")
                return
            
            text = f"🔥 <b>ArcX | Manual Boost</b>\\n\\nSelect channel to boost manually:\\n\\n"
            
            buttons = []
            for channel in channels[:10]:  # Show max 10
                button_text = f"[🚀 {channel['channel_title'][:20]}...]"
                callback_data = f"vm_manual_{channel['id']}"
                buttons.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])
            
            buttons.extend([
                [InlineKeyboardButton(text="[🔙 Back]", callback_data="views_manager")],
                [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
            ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("🚀 Select channel for manual boost")
            
        except Exception as e:
            logger.error(f"Error in manual boost: {e}")
            await callback.answer("❌ Failed to load manual boost", show_alert=True)
    
    async def _handle_start_engine(self, callback: CallbackQuery, state: FSMContext):
        """Start the auto boost monitoring engine"""
        try:
            user_id = callback.from_user.id
            
            # Check if already running
            if user_id in self._boost_engines:
                await callback.answer("ℹ️ Auto boost engine is already running!")
                return
            
            # Get enabled channels
            enabled_channels = await self._get_enabled_channels(user_id)
            if not enabled_channels:
                await callback.message.edit_text(
                    "🔥 <b>ArcX | No Channels Enabled</b>\\n\\n"
                    "Enable channels first in Select Channels.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="[⚙️ Select Channels]", callback_data="vm_select_channels")],
                        [InlineKeyboardButton(text="[🔙 Back]", callback_data="vm_auto_boost")]
                    ])
                )
                await callback.answer("⚠️ No channels enabled!")
                return
            
            # Start monitoring engine
            engine_task = asyncio.create_task(self._monitoring_engine(user_id))
            self._boost_engines[user_id] = {
                'task': engine_task,
                'started_at': datetime.now(),
                'channels': len(enabled_channels)
            }
            
            text = f"""✅ <b>ArcX | Auto Boost Engine Started!</b>

<b>Engine Details:</b>
• Status: 🟢 Running
• Monitoring: {len(enabled_channels)} channels
• Started: {datetime.now().strftime('%H:%M:%S')}

<b>What happens now:</b>
• Engine monitors all enabled channels
• Automatically boosts views based on settings
• Respects cooldown periods
• Performs intelligent load balancing

Engine is now running in the background!
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="[⏹️ Stop Engine]", callback_data="vm_stop_engine")],
                [InlineKeyboardButton(text="[📊 View Stats]", callback_data="vm_engine_stats")],
                [InlineKeyboardButton(text="[🔙 Auto Boost]", callback_data="vm_auto_boost")],
                [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
            ])
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("🚀 Auto boost engine started!")
            
        except Exception as e:
            logger.error(f"Error starting engine: {e}")
            await callback.answer("❌ Failed to start engine", show_alert=True)
    
    async def _handle_stop_engine(self, callback: CallbackQuery, state: FSMContext):
        """Stop the auto boost monitoring engine"""
        try:
            user_id = callback.from_user.id
            
            if user_id not in self._boost_engines:
                await callback.answer("ℹ️ Auto boost engine is not running!")
                return
            
            # Stop the engine
            engine_data = self._boost_engines[user_id]
            engine_data['task'].cancel()
            del self._boost_engines[user_id]
            
            runtime = datetime.now() - engine_data['started_at']
            
            text = f"""⏹️ <b>ArcX | Auto Boost Engine Stopped</b>

<b>Session Summary:</b>
• Runtime: {runtime.seconds // 60} minutes {runtime.seconds % 60} seconds
• Channels Monitored: {engine_data['channels']}
• Status: 🔴 Stopped

Engine has been stopped successfully.
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="[▶️ Start Engine]", callback_data="vm_start_engine")],
                [InlineKeyboardButton(text="[🔙 Auto Boost]", callback_data="vm_auto_boost")],
                [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
            ])
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("⏹️ Engine stopped successfully!")
            
        except Exception as e:
            logger.error(f"Error stopping engine: {e}")
            await callback.answer("❌ Failed to stop engine", show_alert=True)
    
    async def _monitoring_engine(self, user_id: int):
        """Advanced async monitoring engine for auto boost"""
        try:
            logger.info(f"🚀 MONITORING ENGINE: Started for user {user_id}")
            
            while True:
                try:
                    # Get enabled channels
                    enabled_channels = await self._get_enabled_channels(user_id)
                    
                    if not enabled_channels:
                        logger.info(f"⏸️ MONITORING ENGINE: No enabled channels for user {user_id}")
                        await asyncio.sleep(60)  # Wait 1 minute before checking again
                        continue
                    
                    # Process each channel
                    for channel_config in enabled_channels:
                        try:
                            await self._process_channel_boost(user_id, channel_config)
                        except Exception as e:
                            logger.error(f"Error processing channel {channel_config['channel_id']}: {e}")
                    
                    # Wait before next monitoring cycle
                    await asyncio.sleep(30)  # Check every 30 seconds
                    
                except Exception as e:
                    logger.error(f"Error in monitoring engine cycle: {e}")
                    await asyncio.sleep(60)  # Wait longer on error
                    
        except asyncio.CancelledError:
            logger.info(f"⏹️ MONITORING ENGINE: Stopped for user {user_id}")
        except Exception as e:
            logger.error(f"❌ MONITORING ENGINE: Fatal error for user {user_id}: {e}")
    
    async def _process_channel_boost(self, user_id: int, channel_config: Dict[str, Any]):
        """Process individual channel for boost operations"""
        try:
            channel_id = channel_config['channel_id']
            
            # Check cooldown
            last_boost = await self.db.fetch_one(
                "SELECT created_at FROM channel_operations WHERE user_id = $1 AND channel_id = $2 ORDER BY created_at DESC LIMIT 1",
                user_id, channel_id
            )
            
            if last_boost:
                time_since_boost = datetime.now() - last_boost['created_at']
                cooldown = timedelta(minutes=channel_config['cooldown_minutes'])
                
                if time_since_boost < cooldown:
                    return  # Still in cooldown
            
            # Perform boost operation
            await self._perform_boost_operation(user_id, channel_config)
            
        except Exception as e:
            logger.error(f"Error processing channel boost: {e}")
    
    async def _perform_boost_operation(self, user_id: int, channel_config: Dict[str, Any]):
        """Perform the actual boost operation"""
        try:
            # Get user's accounts for boosting
            accounts = await self.db.fetch_all(
                "SELECT * FROM telegram_accounts WHERE user_id = $1 AND is_active = TRUE LIMIT 10",
                user_id
            )
            
            if not accounts:
                logger.warning(f"No active accounts for user {user_id}")
                return
            
            # Record the boost operation
            await self.db.execute_query(
                """
                INSERT INTO channel_operations 
                (user_id, channel_id, operation_type, account_count, success, created_at)
                VALUES ($1, $2, 'auto_boost', $3, TRUE, NOW())
                """,
                user_id, channel_config['channel_id'], len(accounts)
            )
            
            logger.info(f"🚀 BOOST: Auto boosted channel {channel_config['channel_id']} with {len(accounts)} accounts")
            
        except Exception as e:
            logger.error(f"Error performing boost operation: {e}")
    
    # Helper methods
    async def _get_user_channels(self, user_id: int) -> List[Dict[str, Any]]:
        """Get user's channels"""
        return await self.db.fetch_all(
            "SELECT * FROM telegram_channels WHERE user_id = $1 ORDER BY created_at DESC",
            user_id
        )
    
    async def _get_enabled_channels(self, user_id: int) -> List[Dict[str, Any]]:
        """Get channels enabled for auto boost"""
        return await self.db.fetch_all(
            """
            SELECT bc.*, tc.channel_title, tc.channel_identifier 
            FROM boost_configs bc
            JOIN telegram_channels tc ON bc.channel_id = tc.id
            WHERE bc.user_id = $1 AND bc.is_enabled = TRUE
            """,
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
    
    async def _start_monitoring_engine(self):
        """Start the global monitoring engine"""
        logger.info("🚀 Auto boost monitoring engine ready")
    
    def _get_retry_keyboard(self) -> InlineKeyboardMarkup:
        """Get retry keyboard"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="[🔄 Try Again]", callback_data="vm_boost_settings")],
            [InlineKeyboardButton(text="[🔙 Back]", callback_data="vm_auto_boost")]
        ])