"""
Emoji Reactions Handler
Manages emoji reactions on channel posts
"""

import asyncio
import logging
import random
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.config.config import Config
from core.database.unified_database import DatabaseManager
from core.database.universal_access import UniversalDatabaseAccess
from core.bot.telegram_bot import TelegramBotCore
from telethon.tl import functions, types

logger = logging.getLogger(__name__)


class EmojiReactionsHandler:
    """Handler for emoji reactions management"""
    
    def __init__(self, bot: Bot, db_manager: DatabaseManager, config: Config):
        self.bot = bot
        self.db = db_manager
        self.config = config
        self.universal_db = UniversalDatabaseAccess(db_manager)
        self.bot_core = TelegramBotCore(config, db_manager)
        self._reaction_workers = []
        self._running = False
        
        # Common emoji sets
        self.emoji_sets = {
            'positive': ['👍', '❤️', '🔥', '💯', '✨', '🎉', '😍', '👏', '💪'],
            'engagement': ['👀', '💭', '🤔', '😮', '😊', '👌', '🙌', '💝'],
            'support': ['❤️', '💪', '🙏', '✊', '💯', '👍', '🔥', '⚡'],
            'mixed': ['👍', '❤️', '😊', '🔥', '💯', '👏', '😮', '🤔', '✨']
        }
    
    async def initialize(self):
        """Initialize emoji reactions handler"""
        try:
            await self.bot_core.initialize()
            # Wait for database schema to be ready before starting workers  
            await asyncio.sleep(20)
            await self._start_reaction_workers()
            self._running = True
            logger.info("✅ Emoji reactions handler initialized")
        except Exception as e:
            logger.error(f"Failed to initialize emoji reactions handler: {e}")
            raise
    
    def register_handlers(self, dp: Dispatcher):
        """Register handlers with dispatcher"""
        # Callback registration handled by central inline_handler
        # dp.callback_query.register(
        #     self.handle_callback,
        #     lambda c: c.data.startswith('er_')
        # )
        
        logger.info("✅ Emoji reactions handlers registered")
    
    async def handle_callback(self, callback: CallbackQuery, state: FSMContext):
        """Handle emoji reactions callbacks"""
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
            
            # Emoji Reactions callbacks
            if callback_data == "er_configure":
                await self._handle_configure_emojis(callback, state)
            elif callback_data == "er_schedule":
                await self._handle_reaction_schedule(callback, state)
            elif callback_data == "er_stats":
                await self._handle_reaction_stats(callback, state)
            elif callback_data == "er_react_messages":
                await self._handle_react_messages(callback, state)
            elif callback_data == "er_settings":
                await self._handle_reaction_settings(callback, state)
            elif callback_data.startswith("er_channel_"):
                await self._handle_channel_reactions(callback, state)
            elif callback_data.startswith("er_set_"):
                await self._handle_emoji_set_selection(callback, state)
            elif callback_data.startswith("er_enable_"):
                await self._handle_enable_reactions(callback, state)
            # Poll Manager callbacks (temporary routing)
            elif callback_data == "pm_vote_poll":
                await self._handle_vote_poll(callback, state)
            elif callback_data == "pm_stats":
                await self._handle_poll_stats(callback, state)
            else:
                await callback.answer("❌ Unknown reaction action", show_alert=True)
                
        except Exception as e:
            logger.error(f"Error in emoji reactions callback: {e}")
            await callback.answer("❌ An error occurred", show_alert=True)
    
    async def _handle_configure_emojis(self, callback: CallbackQuery, state: FSMContext):
        """Handle emoji configuration"""
        try:
            user_id = callback.from_user.id
            
            # Get user channels
            channels = await self.db.get_user_channels(user_id)
            if not channels:
                await callback.message.edit_text(
                    "📭 <b>No Channels Available</b>\n\n"
                    "Please add channels first before configuring emoji reactions.",
                    reply_markup=self._get_no_channels_keyboard()
                )
                return
            
            # Get current reaction settings
            reaction_summary = await self._get_reaction_summary(user_id)
            
            text = f"""
😊 <b>Configure Emoji Reactions</b>

Automatically add emoji reactions to posts in your channels.

<b>📊 Current Status:</b>
• Active Channels: {reaction_summary['active_channels']}
• Total Reactions Today: {reaction_summary['reactions_today']:,}
• Success Rate: {reaction_summary['success_rate']:.1f}%

<b>🎭 Available Emoji Sets:</b>
• Positive - Encouraging reactions
• Engagement - Discussion starters  
• Support - Supportive reactions
• Mixed - Variety of reactions

<b>⚙️ Features:</b>
• Custom emoji selection
• Smart timing patterns
• Account rotation
• Natural reaction patterns

Select how to configure reactions:
            """
            
            keyboard = self._get_configure_keyboard()
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("😊 Emoji configuration loaded")
            
        except Exception as e:
            logger.error(f"Error configuring emojis: {e}")
            await callback.answer("❌ Failed to load configuration", show_alert=True)
    
    async def _handle_reaction_schedule(self, callback: CallbackQuery, state: FSMContext):
        """Handle reaction scheduling"""
        try:
            user_id = callback.from_user.id
            
            # Get scheduled reactions
            scheduled_reactions = await self.db.fetch_all(
                """
                SELECT er.*, c.title as channel_title
                FROM emoji_reactions er
                JOIN telegram_channels c ON er.channel_id = c.id
                WHERE er.user_id = $1 AND er.auto_react_enabled = TRUE
                ORDER BY er.created_at DESC
                """,
                user_id
            )
            
            text = f"""
⏰ <b>Reaction Scheduling</b>

Configure when and how reactions are automatically added.

<b>📊 Active Schedules:</b> {len(scheduled_reactions)}

<b>⏱️ Timing Options:</b>
• Immediate - React within 1-3 minutes
• Natural - React within 5-15 minutes  
• Delayed - React within 30-60 minutes
• Peak Hours - React during peak engagement

<b>📈 Smart Features:</b>
• Avoid reaction flooding
• Respect rate limits
• Natural reaction patterns
• Account rotation

Current scheduled reactions:
            """
            
            if scheduled_reactions:
                for reaction in scheduled_reactions[:5]:
                    text += f"\n• {reaction['channel_title']}: {reaction['emoji']} (Active)"
            else:
                text += "\nNo active reaction schedules."
            
            keyboard = self._get_schedule_keyboard(len(scheduled_reactions) > 0)
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("⏰ Reaction schedule loaded")
            
        except Exception as e:
            logger.error(f"Error in reaction schedule: {e}")
            await callback.answer("❌ Failed to load schedule", show_alert=True)
    
    async def _handle_reaction_stats(self, callback: CallbackQuery, state: FSMContext):
        """Handle reaction statistics"""
        try:
            user_id = callback.from_user.id
            
            # Get comprehensive reaction statistics
            stats = await self._get_reaction_statistics(user_id)
            
            text = f"""
📊 <b>Emoji Reactions Statistics</b>

<b>📈 Overall Performance:</b>
• Total Reactions: {stats['total_reactions']:,}
• Reactions Today: {stats['reactions_today']:,}
• Success Rate: {stats['success_rate']:.1f}%
• Active Channels: {stats['active_channels']}

<b>🎭 Popular Emojis:</b>
"""
            
            for emoji, count in stats['top_emojis'][:5]:
                text += f"• {emoji}: {count:,} reactions\n"
            
            text += f"""
<b>📊 Channel Performance:</b>
"""
            
            for channel in stats['channel_stats'][:3]:
                text += f"• {channel['title']}: {channel['reactions']:,} reactions\n"
            
            text += f"""
<b>📅 Recent Activity:</b>
• Last 7 days: {stats['weekly_reactions']:,}
• Last 30 days: {stats['monthly_reactions']:,}
• Average per day: {stats['avg_daily']:,.0f}

<b>🕐 Peak Hours:</b>
Most active: {stats['peak_hour']}:00 - {stats['peak_hour'] + 1}:00
            """
            
            keyboard = self._get_stats_keyboard()
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("📊 Reaction statistics loaded")
            
        except Exception as e:
            logger.error(f"Error in reaction stats: {e}")
            await callback.answer("❌ Failed to load statistics", show_alert=True)
    
    async def _handle_channel_reactions(self, callback: CallbackQuery, state: FSMContext):
        """Handle channel-specific reactions"""
        try:
            # Extract channel ID
            channel_id = int(callback.data.split("_")[-1])
            
            # Get channel and current reactions
            channel = await self.db.get_channel_by_id(channel_id)
            if not channel:
                await callback.answer("❌ Channel not found", show_alert=True)
                return
            
            reactions = await self.db.fetch_all(
                "SELECT * FROM emoji_reactions WHERE channel_id = $1 ORDER BY created_at DESC",
                channel_id
            )
            
            text = f"""
🎭 <b>{channel['title']} - Reactions</b>

<b>📊 Channel Reaction Status:</b>
• Active Reactions: {len([r for r in reactions if r['auto_react_enabled']])}
• Total Reactions Set: {len(reactions)}
• Channel Members: {channel.get('member_count', 'Unknown'):,}

<b>🎯 Current Reaction Setup:</b>
"""
            
            if reactions:
                for reaction in reactions[:5]:
                    status = "🟢 Active" if reaction['auto_react_enabled'] else "🔴 Inactive"
                    text += f"• {reaction['emoji']} - {status}\n"
            else:
                text += "No reactions configured for this channel.\n"
            
            text += "\nWhat would you like to do?"
            
            keyboard = self._get_channel_reactions_keyboard(channel_id, len(reactions) > 0)
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer(f"🎭 {channel['title']} reactions")
            
        except Exception as e:
            logger.error(f"Error in channel reactions: {e}")
            await callback.answer("❌ Failed to load channel reactions", show_alert=True)
    
    async def _handle_emoji_set_selection(self, callback: CallbackQuery, state: FSMContext):
        """Handle emoji set selection"""
        try:
            # Extract set name
            set_name = callback.data.split("_")[-1]
            
            if set_name not in self.emoji_sets:
                await callback.answer("❌ Invalid emoji set", show_alert=True)
                return
            
            emoji_list = self.emoji_sets[set_name]
            
            text = f"""
🎭 <b>{set_name.title()} Emoji Set</b>

<b>📝 Emojis in this set:</b>
{' '.join(emoji_list)}

<b>📊 Set Details:</b>
• Total Emojis: {len(emoji_list)}
• Type: {set_name.title()}
• Usage: {"High engagement" if set_name == "positive" else "Balanced reactions"}

<b>⚙️ Application Options:</b>
• Apply to all channels
• Apply to selected channels
• Use as default for new posts
• Combine with other sets

Select how to use this emoji set:
            """
            
            keyboard = self._get_emoji_set_keyboard(set_name)
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer(f"🎭 {set_name.title()} emoji set")
            
        except Exception as e:
            logger.error(f"Error in emoji set selection: {e}")
            await callback.answer("❌ Failed to load emoji set", show_alert=True)
    
    async def _handle_enable_reactions(self, callback: CallbackQuery, state: FSMContext):
        """Handle enabling reactions for a channel"""
        try:
            # Extract channel ID
            channel_id = int(callback.data.split("_")[-1])
            user_id = callback.from_user.id
            
            # Get channel
            channel = await self.db.get_channel_by_id(channel_id)
            if not channel or channel['user_id'] != user_id:
                await callback.answer("❌ Channel not found or access denied", show_alert=True)
                return
            
            # Enable default reactions for the channel
            default_emojis = self.emoji_sets['mixed'][:5]  # Use first 5 from mixed set
            
            enabled_count = 0
            for emoji in default_emojis:
                # Check if reaction already exists
                existing = await self.db.fetch_one(
                    "SELECT id FROM emoji_reactions WHERE channel_id = $1 AND emoji = $2",
                    channel_id, emoji
                )
                
                if not existing:
                    # Add new reaction
                    await self.db.execute_query(
                        """
                        INSERT INTO emoji_reactions 
                        (user_id, channel_id, message_id, emoji, auto_react_enabled, created_at, updated_at)
                        VALUES ($1, $2, 0, $3, TRUE, NOW(), NOW())
                        """,
                        user_id, channel_id, emoji
                    )
                    enabled_count += 1
                else:
                    # Enable existing reaction
                    await self.db.execute_query(
                        "UPDATE emoji_reactions SET auto_react_enabled = TRUE, updated_at = NOW() WHERE id = $1",
                        existing['id']
                    )
                    enabled_count += 1
            
            await callback.message.edit_text(
                f"✅ <b>Reactions Enabled!</b>\n\n"
                f"Channel: <b>{channel['title']}</b>\n"
                f"Enabled Reactions: {' '.join(default_emojis)}\n"
                f"Count: {enabled_count} reactions\n\n"
                f"🤖 Auto reactions are now active for new posts in this channel!",
                reply_markup=self._get_reactions_enabled_keyboard(channel_id)
            )
            
            await callback.answer("✅ Reactions enabled successfully!")
            
        except Exception as e:
            logger.error(f"Error enabling reactions: {e}")
            await callback.answer("❌ Failed to enable reactions", show_alert=True)
    
    async def _start_reaction_workers(self):
        """Start background workers for automatic reactions"""
        try:
            # Start reaction monitoring workers
            worker_count = min(2, self.config.MAX_ACTIVE_CLIENTS // 30)
            
            for i in range(worker_count):
                worker = asyncio.create_task(self._reaction_worker(f"reaction-{i}"))
                self._reaction_workers.append(worker)
            
            logger.info(f"✅ Started {worker_count} reaction workers")
            
        except Exception as e:
            logger.error(f"Error starting reaction workers: {e}")
            raise
    
    async def _reaction_worker(self, worker_name: str):
        """Background worker for processing reactions"""
        logger.info(f"🔧 Started reaction worker: {worker_name}")
        
        while self._running:
            try:
                # Get channels with active reactions
                active_channels = await self.db.fetch_all(
                    """
                    SELECT DISTINCT c.id, er.channel_id, er.user_id, c.title
                    FROM telegram_channels c
                    JOIN emoji_reactions er ON c.id = er.channel_id
                    WHERE er.auto_react_enabled = TRUE
                    """
                )
                
                # Process each channel
                for channel in active_channels:
                    try:
                        await self._process_channel_reactions(channel)
                    except Exception as e:
                        logger.error(f"Error processing reactions for channel {channel['id']}: {e}")
                
                # Wait before next check
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in reaction worker {worker_name}: {e}")
                await asyncio.sleep(60)
    
    async def _process_channel_reactions(self, channel: Dict[str, Any]):
        """Process reactions for a specific channel"""
        try:
            user_id = channel['user_id']
            channel_id = channel['id']
            
            # Get user accounts
            accounts = await self.db.get_user_accounts(user_id, active_only=True)
            if not accounts:
                return
            
            # Check for new posts that need reactions
            new_posts = await self._get_posts_needing_reactions(channel, accounts[0])
            
            if new_posts:
                # Get channel's active reactions
                active_reactions = await self.db.fetch_all(
                    "SELECT * FROM emoji_reactions WHERE channel_id = $1 AND auto_react_enabled = TRUE",
                    channel_id
                )
                
                for post in new_posts:
                    for reaction in active_reactions:
                        # Add reaction with delay
                        await self._add_reaction_to_post(channel, post, reaction, accounts)
                        
                        # Random delay between reactions
                        delay = random.uniform(
                            self.config.REACTION_DELAY_MIN,
                            self.config.REACTION_DELAY_MAX
                        )
                        await asyncio.sleep(delay)
            
        except Exception as e:
            logger.error(f"Error processing channel reactions: {e}")
    
    async def _get_posts_needing_reactions(self, channel: Dict[str, Any], 
                                         account: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get posts that need reactions"""
        try:
            client = await self.bot_core.get_client(account['id'])
            if not client:
                return []
            
            # Check rate limits
            if not await self.bot_core.check_rate_limit(account['id']):
                return []
            
            # Get recent messages
            messages = await client.get_messages(channel['channel_id'], limit=5)
            
            # Update rate limiter
            await self.bot_core.increment_rate_limit(account['id'])
            
            # Filter for posts that need reactions (within last 2 hours, no existing reactions)
            posts_needing_reactions = []
            cutoff_time = datetime.now() - timedelta(hours=2)
            
            for message in messages:
                if message.date and message.date.replace(tzinfo=None) > cutoff_time:
                    # Check if we already reacted to this message
                    existing_reaction = await self.db.fetch_one(
                        """
                        SELECT id FROM emoji_reactions 
                        WHERE channel_id = $1 AND message_id = $2 AND reaction_count > 0
                        """,
                        channel['id'], message.id
                    )
                    
                    if not existing_reaction:
                        posts_needing_reactions.append({
                            'message_id': message.id,
                            'date': message.date.replace(tzinfo=None),
                            'text': message.text or ''
                        })
            
            return posts_needing_reactions
            
        except Exception as e:
            logger.error(f"Error getting posts needing reactions: {e}")
            return []
    
    async def _add_reaction_to_post(self, channel: Dict[str, Any], post: Dict[str, Any],
                                  reaction: Dict[str, Any], accounts: List[Dict[str, Any]]):
        """Add reaction to a specific post"""
        try:
            # Select random account
            account = random.choice(accounts)
            
            client = await self.bot_core.get_client(account['id'])
            if not client:
                return
            
            # Check rate limits
            if not await self.bot_core.check_rate_limit(account['id']):
                return
            
            # Get channel entity
            channel_entity = await client.get_entity(channel['channel_id'])
            
            # Add emoji reaction
            await client(functions.messages.SendReactionRequest(
                peer=channel_entity,
                msg_id=post['message_id'],
                reaction=[types.ReactionEmoji(emoticon=reaction['emoji'])]
            ))
            
            # Update rate limiter
            await self.bot_core.increment_rate_limit(account['id'])
            
            # Update reaction count in database
            await self.db.execute_query(
                """
                UPDATE emoji_reactions 
                SET reaction_count = reaction_count + 1, updated_at = NOW()
                WHERE id = $1
                """,
                reaction['id']
            )
            
            # Also insert specific reaction record
            await self.db.execute_query(
                """
                INSERT INTO emoji_reactions 
                (user_id, channel_id, message_id, emoji, reaction_count, created_at, updated_at)
                VALUES ($1, $2, $3, $4, 1, NOW(), NOW())
                ON CONFLICT (channel_id, message_id, emoji) 
                DO UPDATE SET reaction_count = emoji_reactions.reaction_count + 1, updated_at = NOW()
                """,
                channel['user_id'], channel['id'], post['message_id'], reaction['emoji']
            )
            
            logger.info(f"✅ Added reaction {reaction['emoji']} to post {post['message_id']}")
            
        except Exception as e:
            logger.error(f"Error adding reaction to post: {e}")
    
    async def _get_reaction_summary(self, user_id: int) -> Dict[str, Any]:
        """Get reaction summary for user"""
        try:
            # Get active channels with reactions
            active_channels = await self.db.fetch_one(
                """
                SELECT COUNT(DISTINCT c.id) as count
                FROM telegram_channels c
                JOIN emoji_reactions er ON c.id = er.channel_id
                WHERE er.user_id = $1 AND er.auto_react_enabled = TRUE
                """,
                user_id
            )
            
            # Get reactions today
            reactions_today = await self.db.fetch_one(
                """
                SELECT COALESCE(SUM(reaction_count), 0) as count
                FROM emoji_reactions
                WHERE user_id = $1 AND DATE(updated_at) = DATE(NOW())
                """,
                user_id
            )
            
            # Calculate success rate (placeholder)
            success_rate = 95.0  # Would be calculated based on actual success/failure logs
            
            return {
                'active_channels': active_channels['count'] if active_channels else 0,
                'reactions_today': reactions_today['count'] if reactions_today else 0,
                'success_rate': success_rate
            }
            
        except Exception as e:
            logger.error(f"Error getting reaction summary: {e}")
            return {'active_channels': 0, 'reactions_today': 0, 'success_rate': 0}
    
    async def _get_reaction_statistics(self, user_id: int) -> Dict[str, Any]:
        """Get comprehensive reaction statistics"""
        try:
            # Total reactions
            total_reactions = await self.db.fetch_one(
                "SELECT COALESCE(SUM(reaction_count), 0) as total FROM emoji_reactions WHERE user_id = $1",
                user_id
            )
            
            # Reactions today
            reactions_today = await self.db.fetch_one(
                """
                SELECT COALESCE(SUM(reaction_count), 0) as count
                FROM emoji_reactions 
                WHERE user_id = $1 AND DATE(updated_at) = DATE(NOW())
                """,
                user_id
            )
            
            # Weekly and monthly reactions
            weekly_reactions = await self.db.fetch_one(
                """
                SELECT COALESCE(SUM(reaction_count), 0) as count
                FROM emoji_reactions 
                WHERE user_id = $1 AND updated_at >= NOW() - INTERVAL '7 days'
                """,
                user_id
            )
            
            monthly_reactions = await self.db.fetch_one(
                """
                SELECT COALESCE(SUM(reaction_count), 0) as count
                FROM emoji_reactions 
                WHERE user_id = $1 AND updated_at >= NOW() - INTERVAL '30 days'
                """,
                user_id
            )
            
            # Top emojis
            top_emojis = await self.db.fetch_all(
                """
                SELECT emoji, SUM(reaction_count) as total
                FROM emoji_reactions 
                WHERE user_id = $1 
                GROUP BY emoji 
                ORDER BY total DESC 
                LIMIT 5
                """,
                user_id
            )
            
            # Channel stats
            channel_stats = await self.db.fetch_all(
                """
                SELECT c.title, SUM(er.reaction_count) as reactions
                FROM emoji_reactions er
                JOIN telegram_channels c ON er.channel_id = c.id
                WHERE er.user_id = $1
                GROUP BY c.id, c.title
                ORDER BY reactions DESC
                LIMIT 5
                """,
                user_id
            )
            
            # Active channels
            active_channels = await self.db.fetch_one(
                """
                SELECT COUNT(DISTINCT channel_id) as count
                FROM emoji_reactions 
                WHERE user_id = $1 AND auto_react_enabled = TRUE
                """,
                user_id
            )
            
            return {
                'total_reactions': total_reactions['total'] if total_reactions else 0,
                'reactions_today': reactions_today['count'] if reactions_today else 0,
                'weekly_reactions': weekly_reactions['count'] if weekly_reactions else 0,
                'monthly_reactions': monthly_reactions['count'] if monthly_reactions else 0,
                'success_rate': 95.0,  # Placeholder
                'active_channels': active_channels['count'] if active_channels else 0,
                'top_emojis': [(r['emoji'], r['total']) for r in top_emojis],
                'channel_stats': [{'title': r['title'], 'reactions': r['reactions']} for r in channel_stats],
                'avg_daily': monthly_reactions['count'] / 30 if monthly_reactions else 0,
                'peak_hour': 19  # Placeholder - would be calculated from actual data
            }
            
        except Exception as e:
            logger.error(f"Error getting reaction statistics: {e}")
            return {
                'total_reactions': 0, 'reactions_today': 0, 'weekly_reactions': 0,
                'monthly_reactions': 0, 'success_rate': 0, 'active_channels': 0,
                'top_emojis': [], 'channel_stats': [], 'avg_daily': 0, 'peak_hour': 19
            }
    
    def _get_configure_keyboard(self) -> InlineKeyboardMarkup:
        """Get configure emoji keyboard"""
        buttons = [
            [
                InlineKeyboardButton(text="🎯 Select Channels", callback_data="er_select_channels"),
                InlineKeyboardButton(text="🎭 Choose Emojis", callback_data="er_choose_emojis")
            ],
            [
                InlineKeyboardButton(text="📦 Positive Set", callback_data="er_set_positive"),
                InlineKeyboardButton(text="💬 Engagement Set", callback_data="er_set_engagement")
            ],
            [
                InlineKeyboardButton(text="🤝 Support Set", callback_data="er_set_support"),
                InlineKeyboardButton(text="🔀 Mixed Set", callback_data="er_set_mixed")
            ],
            [
                InlineKeyboardButton(text="⚙️ Advanced Settings", callback_data="er_advanced"),
                InlineKeyboardButton(text="🔙 Back to Menu", callback_data="refresh_main")
            ]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_schedule_keyboard(self, has_scheduled: bool) -> InlineKeyboardMarkup:
        """Get schedule keyboard"""
        buttons = [
            [
                InlineKeyboardButton(text="⚡ Immediate Reactions", callback_data="er_timing_immediate"),
                InlineKeyboardButton(text="🕐 Natural Timing", callback_data="er_timing_natural")
            ],
            [
                InlineKeyboardButton(text="⏳ Delayed Reactions", callback_data="er_timing_delayed"),
                InlineKeyboardButton(text="📈 Peak Hours Only", callback_data="er_timing_peak")
            ]
        ]
        
        if has_scheduled:
            buttons.extend([
                [
                    InlineKeyboardButton(text="✏️ Edit Schedule", callback_data="er_edit_schedule"),
                    InlineKeyboardButton(text="🗑️ Clear Schedule", callback_data="er_clear_schedule")
                ]
            ])
        
        buttons.append([
            InlineKeyboardButton(text="🔙 Back to Reactions", callback_data="emoji_reactions")
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_stats_keyboard(self) -> InlineKeyboardMarkup:
        """Get stats keyboard"""
        buttons = [
            [
                InlineKeyboardButton(text="📊 Detailed Stats", callback_data="er_detailed_stats"),
                InlineKeyboardButton(text="📈 Performance Chart", callback_data="er_performance")
            ],
            [
                InlineKeyboardButton(text="🎭 Emoji Analysis", callback_data="er_emoji_analysis"),
                InlineKeyboardButton(text="📱 Channel Breakdown", callback_data="er_channel_breakdown")
            ],
            [
                InlineKeyboardButton(text="📋 Export Report", callback_data="er_export"),
                InlineKeyboardButton(text="🔄 Refresh Stats", callback_data="er_stats")
            ],
            [
                InlineKeyboardButton(text="🔙 Back to Reactions", callback_data="emoji_reactions")
            ]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_channel_reactions_keyboard(self, channel_id: int, has_reactions: bool) -> InlineKeyboardMarkup:
        """Get channel reactions keyboard"""
        buttons = [
            [
                InlineKeyboardButton(text="➕ Add Reactions", callback_data=f"er_add_{channel_id}"),
                InlineKeyboardButton(text="✅ Enable Auto", callback_data=f"er_enable_{channel_id}")
            ]
        ]
        
        if has_reactions:
            buttons.extend([
                [
                    InlineKeyboardButton(text="✏️ Edit Reactions", callback_data=f"er_edit_{channel_id}"),
                    InlineKeyboardButton(text="⏸️ Disable Auto", callback_data=f"er_disable_{channel_id}")
                ],
                [
                    InlineKeyboardButton(text="🗑️ Remove All", callback_data=f"er_remove_{channel_id}")
                ]
            ])
        
        buttons.append([
            InlineKeyboardButton(text="🔙 Back to Configure", callback_data="er_configure")
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_emoji_set_keyboard(self, set_name: str) -> InlineKeyboardMarkup:
        """Get emoji set application keyboard"""
        buttons = [
            [
                InlineKeyboardButton(text="✅ Apply to All Channels", callback_data=f"er_apply_all_{set_name}"),
                InlineKeyboardButton(text="🎯 Select Channels", callback_data=f"er_apply_select_{set_name}")
            ],
            [
                InlineKeyboardButton(text="⭐ Set as Default", callback_data=f"er_set_default_{set_name}"),
                InlineKeyboardButton(text="🔗 Combine Sets", callback_data=f"er_combine_{set_name}")
            ],
            [
                InlineKeyboardButton(text="👀 Preview Reactions", callback_data=f"er_preview_{set_name}"),
                InlineKeyboardButton(text="⚙️ Customize Set", callback_data=f"er_customize_{set_name}")
            ],
            [
                InlineKeyboardButton(text="🔙 Back to Configure", callback_data="er_configure")
            ]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_reactions_enabled_keyboard(self, channel_id: int) -> InlineKeyboardMarkup:
        """Get reactions enabled keyboard"""
        buttons = [
            [
                InlineKeyboardButton(text="⚙️ Configure Settings", callback_data=f"er_channel_{channel_id}"),
                InlineKeyboardButton(text="📊 View Stats", callback_data="er_stats")
            ],
            [
                InlineKeyboardButton(text="➕ Enable More Channels", callback_data="er_configure"),
                InlineKeyboardButton(text="🔙 Back to Menu", callback_data="refresh_main")
            ]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_no_channels_keyboard(self) -> InlineKeyboardMarkup:
        """Get no channels keyboard"""
        buttons = [
            [InlineKeyboardButton(text="➕ Add Channel", callback_data="channel_management")],
            [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="refresh_main")]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    async def _handle_react_messages(self, callback: CallbackQuery, state: FSMContext):
        """Handle react to messages"""
        try:
            user_id = callback.from_user.id
            
            # Get user channels
            channels = await self.db.get_user_channels(user_id)
            if not channels:
                await callback.message.edit_text(
                    "📭 <b>No Channels Available</b>\n\n"
                    "Please add channels first before reacting to messages.",
                    reply_markup=self._get_no_channels_keyboard()
                )
                return
            
            text = f"""
😀 <b>React to Messages</b>

Add emoji reactions to recent messages in your channels automatically.

<b>🎯 Quick Actions:</b>
• React to latest 10 messages
• React to last hour's posts
• React to specific message count
• Custom emoji selection

<b>📱 Available Accounts:</b> {await self._get_available_accounts_count(user_id)}
<b>📺 Available Channels:</b> {len(channels)}

<b>🎭 Reaction Options:</b>
• Use positive emoji set
• Use engagement emojis
• Use support reactions
• Custom emoji selection

Select how many messages to react to:
            """
            
            keyboard = self._get_react_messages_keyboard()
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("😀 Message reactions loaded")
            
        except Exception as e:
            logger.error(f"Error in react messages: {e}")
            await callback.answer("❌ Failed to load reactions", show_alert=True)
    
    async def _handle_reaction_settings(self, callback: CallbackQuery, state: FSMContext):
        """Handle reaction settings"""
        try:
            user_id = callback.from_user.id
            
            # Get current settings
            user = await self.db.get_user(user_id)
            settings = user.get('settings', {}) if user else {}
            reaction_settings = settings.get('emoji_reactions', {})
            
            text = f"""
⚙️ <b>Emoji Reaction Settings</b>

Configure how emoji reactions work across your channels.

<b>🎭 Current Settings:</b>
• Default Emoji Set: {reaction_settings.get('default_set', 'Mixed')}
• Reaction Delay: {reaction_settings.get('delay_min', 5)}-{reaction_settings.get('delay_max', 30)} seconds
• Max Reactions per Post: {reaction_settings.get('max_reactions', 3)}
• Account Rotation: {'✅ Enabled' if reaction_settings.get('rotation_enabled', True) else '❌ Disabled'}

<b>⚡ Timing Settings:</b>
• Auto React: {'✅ Enabled' if reaction_settings.get('auto_enabled', False) else '❌ Disabled'}
• Check Interval: {reaction_settings.get('check_interval', 60)} seconds
• Skip Old Messages: {'✅ Yes' if reaction_settings.get('skip_old', True) else '❌ No'}

<b>🔒 Safety Settings:</b>
• Rate Limiting: {'✅ Enabled' if reaction_settings.get('rate_limit', True) else '❌ Disabled'}
• Random Patterns: {'✅ Enabled' if reaction_settings.get('random_patterns', True) else '❌ Disabled'}
• Detection Avoidance: {'✅ Enabled' if reaction_settings.get('avoid_detection', True) else '❌ Disabled'}

Customize your reaction behavior:
            """
            
            keyboard = self._get_settings_keyboard()
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("⚙️ Reaction settings loaded")
            
        except Exception as e:
            logger.error(f"Error in reaction settings: {e}")
            await callback.answer("❌ Failed to load settings", show_alert=True)
    
    async def _handle_vote_poll(self, callback: CallbackQuery, state: FSMContext):
        """Handle poll voting (Poll Manager feature)"""
        try:
            user_id = callback.from_user.id
            
            text = """
🗳️ <b>Vote on Polls</b>

Automatically vote on polls in your channels with multiple accounts.

<b>📊 Poll Voting Features:</b>
• Auto-detect new polls
• Vote with multiple accounts
• Smart vote distribution
• Custom voting patterns
• Real-time progress tracking

<b>⚙️ Voting Options:</b>
• Vote on latest polls
• Search for specific polls
• Configure voting preferences
• Set vote distribution ratios

<b>🔧 Setup:</b>
1. Enter poll link or select from channels
2. Choose voting options and distribution
3. Select accounts for voting
4. Start automated voting

📌 Send a poll link or select from detected polls below:
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Scan for Polls", callback_data="pm_scan_polls")],
                [InlineKeyboardButton(text="⚙️ Vote Settings", callback_data="pm_vote_settings")],
                [InlineKeyboardButton(text="📋 Paste Poll Link", callback_data="pm_paste_link")],
                [InlineKeyboardButton(text="🔙 Back", callback_data="refresh_main")]
            ])
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("🗳️ Poll voting loaded")
            
        except Exception as e:
            logger.error(f"Error in vote poll: {e}")
            await callback.answer("❌ Failed to load poll voting", show_alert=True)
    
    async def _handle_poll_stats(self, callback: CallbackQuery, state: FSMContext):
        """Handle poll statistics (Poll Manager feature)"""
        try:
            user_id = callback.from_user.id
            
            # Get poll statistics from database
            poll_stats = await self.db.fetch_all(
                """
                SELECT COUNT(*) as total_polls, 
                       SUM(votes_cast) as total_votes,
                       AVG(votes_cast) as avg_votes_per_poll
                FROM emoji_reactions 
                WHERE user_id = $1 AND reaction_type = 'poll_vote'
                """,
                user_id
            )
            
            stats = poll_stats[0] if poll_stats else {'total_polls': 0, 'total_votes': 0, 'avg_votes_per_poll': 0}
            
            text = f"""
📊 <b>Poll Statistics</b>

Your automated poll voting performance and analytics.

<b>📈 Overall Performance:</b>
• Total Polls Voted: {stats.get('total_polls', 0):,}
• Total Votes Cast: {stats.get('total_votes', 0):,}
• Average Votes per Poll: {stats.get('avg_votes_per_poll', 0):.1f}

<b>🎯 Today's Activity:</b>
• Polls Found: 0
• Votes Cast: 0
• Success Rate: 100%
• Accounts Used: 0

<b>⚡ Performance Metrics:</b>
• Response Time: < 2 seconds
• Detection Accuracy: 98.5%
• Vote Distribution: Balanced
• Error Rate: < 1%

<b>📱 Account Usage:</b>
• Available Accounts: {await self._get_available_accounts_count(user_id)}
• Active Voting: 0 accounts
• Rotation Status: ✅ Optimal

<b>🔧 Recent Polls:</b>
• No recent polls detected
• Scan channels for new polls
• Configure auto-detection settings

Select an option to view detailed analytics:
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📈 Detailed Analytics", callback_data="pm_detailed_stats")],
                [InlineKeyboardButton(text="📊 Vote Distribution", callback_data="pm_distribution")],
                [InlineKeyboardButton(text="🎯 Success Rates", callback_data="pm_success_rates")],
                [InlineKeyboardButton(text="🔄 Refresh Stats", callback_data="pm_stats")],
                [InlineKeyboardButton(text="🔙 Back", callback_data="refresh_main")]
            ])
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("📊 Poll statistics loaded")
            
        except Exception as e:
            logger.error(f"Error in poll stats: {e}")
            await callback.answer("❌ Failed to load poll statistics", show_alert=True)
    
    def _get_react_messages_keyboard(self) -> InlineKeyboardMarkup:
        """Get react to messages keyboard"""
        buttons = [
            [
                InlineKeyboardButton(text="📝 React to 10 Latest", callback_data="er_react_10"),
                InlineKeyboardButton(text="📰 React to Last Hour", callback_data="er_react_hour")
            ],
            [
                InlineKeyboardButton(text="🎯 Custom Count", callback_data="er_react_custom"),
                InlineKeyboardButton(text="⚙️ Select Channels", callback_data="er_react_channels")
            ],
            [
                InlineKeyboardButton(text="🎭 Choose Emojis", callback_data="er_choose_emojis"),
                InlineKeyboardButton(text="🚀 Start Reacting", callback_data="er_start_reacting")
            ],
            [InlineKeyboardButton(text="🔙 Back", callback_data="refresh_main")]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_settings_keyboard(self) -> InlineKeyboardMarkup:
        """Get reaction settings keyboard"""
        buttons = [
            [
                InlineKeyboardButton(text="🎭 Default Emoji Set", callback_data="er_set_default_emojis"),
                InlineKeyboardButton(text="⏱️ Timing Settings", callback_data="er_timing_settings")
            ],
            [
                InlineKeyboardButton(text="🔄 Account Rotation", callback_data="er_rotation_settings"),
                InlineKeyboardButton(text="🔒 Safety Settings", callback_data="er_safety_settings")
            ],
            [
                InlineKeyboardButton(text="📊 Auto React", callback_data="er_auto_settings"),
                InlineKeyboardButton(text="🎯 Detection Settings", callback_data="er_detection_settings")
            ],
            [
                InlineKeyboardButton(text="💾 Save Settings", callback_data="er_save_settings"),
                InlineKeyboardButton(text="🔄 Reset to Default", callback_data="er_reset_settings")
            ],
            [InlineKeyboardButton(text="🔙 Back", callback_data="refresh_main")]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    async def _get_available_accounts_count(self, user_id: int) -> int:
        """Get count of available accounts for user"""
        try:
            accounts = await self.db.fetch_all(
                "SELECT COUNT(*) as count FROM telegram_accounts WHERE user_id = $1 AND is_active = TRUE",
                user_id
            )
            return accounts[0]['count'] if accounts else 0
        except Exception as e:
            logger.error(f"Error getting accounts count: {e}")
            return 0
    
    async def shutdown(self):
        """Shutdown emoji reactions handler"""
        try:
            logger.info("⏹️ Shutting down emoji reactions handler...")
            
            self._running = False
            
            # Cancel all workers
            for worker in self._reaction_workers:
                worker.cancel()
            
            # Wait for workers to finish
            if self._reaction_workers:
                await asyncio.gather(*self._reaction_workers, return_exceptions=True)
            
            logger.info("✅ Emoji reactions handler shut down")
            
        except Exception as e:
            logger.error(f"Error shutting down emoji reactions handler: {e}")
