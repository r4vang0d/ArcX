"""
Add Channel Handler
Handles the process of adding new channels
"""

import logging
from typing import Dict, Any
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from core.config.config import Config
from core.database.unified_database import DatabaseManager
from ..states import ChannelManagementStates
from ..utils import ChannelValidator

logger = logging.getLogger(__name__)


class AddChannelHandler:
    """Handler for adding new channels"""
    
    def __init__(self, bot: Bot, db_manager: DatabaseManager, config: Config):
        self.bot = bot
        self.db = db_manager
        self.config = config
        self.validator = ChannelValidator(bot, db_manager, config)
        
    async def initialize(self):
        """Initialize add channel handler"""
        logger.info("✅ Add channel handler initialized")
    
    def register_handlers(self, dp: Dispatcher):
        """Register handlers with dispatcher"""
        # Callback handlers for add channel flow
        dp.callback_query.register(
            self.handle_add_help,
            lambda c: c.data == 'cm_add_help'
        )
        
        dp.callback_query.register(
            self.handle_bulk_add,
            lambda c: c.data == 'cm_bulk_add'
        )
        
        # FSM handlers for bulk adding
        dp.message.register(
            self.handle_bulk_channel_list,
            ChannelManagementStates.waiting_for_channel_list
        )
    
    async def handle_add_help(self, callback: CallbackQuery, state: FSMContext):
        """Show help for adding channels"""
        try:
            help_text = """
❓ <b>How to Add Channels</b>

<b>📝 Supported Formats:</b>

<b>1. Username:</b>
• @channelname
• channelname (without @)

<b>2. Channel Link:</b>
• https://t.me/channelname
• https://telegram.me/channelname

<b>3. Channel ID:</b>
• -1001234567890

<b>📋 Requirements:</b>
• You must be a member of the channel
• Channel should be public or you need admin rights
• Bot requires read access to messages

<b>🔧 Troubleshooting:</b>
• If channel is private, make sure you're an admin
• Check that the channel link is correct
• Ensure you have at least one active Telegram account

<b>💡 Tips:</b>
• Use channel username for best results
• Public channels work better than private ones
• Admin rights allow more features like view boosting

<b>🆘 Need more help?</b>
Contact support if you continue having issues.
            """
            
            from ..keyboards import ChannelManagementKeyboards
            keyboards = ChannelManagementKeyboards()
            
            await callback.message.edit_text(
                help_text,
                reply_markup=keyboards.get_add_channel_retry_keyboard()
            )
            await callback.answer("📚 Help information loaded")
            
        except Exception as e:
            logger.error(f"Error showing add help: {e}")
            await callback.answer("❌ Failed to load help", show_alert=True)
    
    async def handle_bulk_add(self, callback: CallbackQuery, state: FSMContext):
        """Handle bulk channel adding"""
        try:
            text = """
📥 <b>Bulk Add Channels</b>

Add multiple channels at once by providing a list of channel links or usernames.

<b>📝 Format:</b>
Send one channel per line:

@channel1
@channel2
https://t.me/channel3

<b>💡 Tips:</b>
• Maximum 10 channels per batch
• Each channel will be validated individually
• Invalid channels will be skipped with errors shown

Send your channel list now:
            """
            
            from ..keyboards import ChannelManagementKeyboards
            keyboards = ChannelManagementKeyboards()
            
            await callback.message.edit_text(
                text,
                reply_markup=keyboards.get_bulk_add_keyboard()
            )
            await state.set_state(ChannelManagementStates.waiting_for_channel_list)
            await callback.answer("📝 Ready for bulk input")
            
        except Exception as e:
            logger.error(f"Error handling bulk add: {e}")
            await callback.answer("❌ Failed to start bulk add", show_alert=True)
    
    async def handle_bulk_channel_list(self, message: Message, state: FSMContext):
        """Process bulk channel list input"""
        try:
            channel_list = message.text.strip().split('\n')
            channel_list = [ch.strip() for ch in channel_list if ch.strip()]
            
            if len(channel_list) > 10:
                await message.reply("❌ Maximum 10 channels allowed per batch")
                return
            
            results = {
                'success': [],
                'failed': []
            }
            
            status_msg = await message.reply("🔄 Processing channels...")
            
            for i, channel in enumerate(channel_list):
                try:
                    # Update progress
                    await status_msg.edit_text(
                        f"🔄 Processing ({i+1}/{len(channel_list)}): {channel}"
                    )
                    
                    # Validate and add channel
                    result = await self.validator.validate_and_add_channel(channel, message.from_user.id)
                    
                    if result['valid']:
                        results['success'].append(channel)
                    else:
                        results['failed'].append({
                            'channel': channel,
                            'error': result['error']
                        })
                        
                except Exception as e:
                    results['failed'].append({
                        'channel': channel,
                        'error': str(e)
                    })
            
            # Show results
            result_text = f"📊 <b>Bulk Add Results</b>\n\n"
            
            if results['success']:
                result_text += f"✅ <b>Successfully Added ({len(results['success'])}):</b>\n"
                for ch in results['success']:
                    result_text += f"• {ch}\n"
                result_text += "\n"
            
            if results['failed']:
                result_text += f"❌ <b>Failed ({len(results['failed'])}):</b>\n"
                for fail in results['failed']:
                    result_text += f"• {fail['channel']}: {fail['error']}\n"
            
            await status_msg.edit_text(result_text)
            await state.clear()
            
        except Exception as e:
            logger.error(f"Error processing bulk channels: {e}")
            await message.reply("❌ Error processing channel list")
            await state.clear()
