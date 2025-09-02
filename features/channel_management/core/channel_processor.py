"""
Channel Processor
Core channel processing and management logic
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from telethon import TelegramClient
from telethon.tl import types, functions
from telethon.errors import FloodWaitError, ChannelPrivateError

from core.config.config import Config
from core.database.unified_database import DatabaseManager
from core.bot.telegram_bot import TelegramBotCore

logger = logging.getLogger(__name__)


class ChannelProcessor:
    """Core channel processing and management"""
    
    def __init__(self, config: Config, db_manager: DatabaseManager, bot_core=None):
        self.config = config
        self.db = db_manager
        self.bot_core = bot_core if bot_core else TelegramBotCore(config, db_manager)
        self._processing_queue = asyncio.Queue()
        self._workers = []
        self._running = False
        
    async def initialize(self):
        """Initialize channel processor"""
        try:
            # Start processing workers
            await self._start_workers()
            self._running = True
            logger.info("✅ Channel processor initialized")
        except Exception as e:
            logger.error(f"Failed to initialize channel processor: {e}")
            raise
    
    async def _start_workers(self):
        """Start background processing workers"""
        worker_count = min(3, self.config.MAX_ACTIVE_CLIENTS // 10)  # Limit workers
        
        for i in range(worker_count):
            worker = asyncio.create_task(self._processing_worker(f"worker-{i}"))
            self._workers.append(worker)
        
        logger.info(f"✅ Started {worker_count} channel processing workers")
    
    async def _processing_worker(self, worker_name: str):
        """Background worker for processing channel tasks"""
        logger.info(f"🔧 Started channel processing worker: {worker_name}")
        
        while self._running:
            try:
                # Get task from queue with timeout
                task = await asyncio.wait_for(
                    self._processing_queue.get(), 
                    timeout=30.0
                )
                
                # Process the task
                await self._process_task(task, worker_name)
                
                # Mark task as done
                self._processing_queue.task_done()
                
            except asyncio.TimeoutError:
                # No tasks, continue waiting
                continue
            except Exception as e:
                logger.error(f"Error in channel processing worker {worker_name}: {e}")
                await asyncio.sleep(5)  # Brief pause before continuing
    
    async def _process_task(self, task: Dict[str, Any], worker_name: str):
        """Process individual channel task"""
        try:
            task_type = task.get('type')
            task_data = task.get('data', {})
            
            if task_type == 'refresh_channel':
                await self._process_refresh_channel(task_data)
            elif task_type == 'validate_channel':
                await self._process_validate_channel(task_data)
            elif task_type == 'update_analytics':
                await self._process_update_analytics(task_data)
            elif task_type == 'batch_refresh':
                await self._process_batch_refresh(task_data)
            else:
                logger.warning(f"Unknown task type: {task_type}")
                
        except Exception as e:
            logger.error(f"Error processing channel task: {e}")
    
    async def queue_channel_refresh(self, channel_id: int, priority: int = 5):
        """Queue channel refresh task"""
        task = {
            'type': 'refresh_channel',
            'data': {'channel_id': channel_id},
            'priority': priority,
            'queued_at': datetime.now()
        }
        await self._processing_queue.put(task)
    
    async def queue_channel_validation(self, channel_id: int, account_id: int):
        """Queue channel validation task"""
        task = {
            'type': 'validate_channel',
            'data': {'channel_id': channel_id, 'account_id': account_id},
            'priority': 8,
            'queued_at': datetime.now()
        }
        await self._processing_queue.put(task)
    
    async def queue_analytics_update(self, channel_id: int, metrics: Dict[str, Any]):
        """Queue analytics update task"""
        task = {
            'type': 'update_analytics',
            'data': {'channel_id': channel_id, 'metrics': metrics},
            'priority': 3,
            'queued_at': datetime.now()
        }
        await self._processing_queue.put(task)
    
    async def queue_batch_refresh(self, user_id: int):
        """Queue batch refresh for all user channels"""
        task = {
            'type': 'batch_refresh',
            'data': {'user_id': user_id},
            'priority': 2,
            'queued_at': datetime.now()
        }
        await self._processing_queue.put(task)
    
    async def _process_refresh_channel(self, task_data: Dict[str, Any]):
        """Process channel refresh task"""
        try:
            channel_id = task_data['channel_id']
            
            # Get channel from database
            channel = await self.db.get_channel_by_id(channel_id)
            if not channel:
                logger.warning(f"Channel {channel_id} not found for refresh")
                return
            
            # Get user's accounts
            accounts = await self.db.get_user_accounts(channel['user_id'], active_only=True)
            if not accounts:
                logger.warning(f"No active accounts for user {channel['user_id']}")
                return
            
            # Try to refresh with available accounts
            success = False
            for account in accounts:
                try:
                    client = await self.bot_core.get_client(account['id'])
                    if not client:
                        continue
                    
                    # Check rate limits
                    if not await self.bot_core.check_rate_limit(account['id']):
                        continue
                    
                    # Get updated channel information
                    entity = await client.get_entity(channel['channel_id'])
                    full_channel = await client(functions.channels.GetFullChannelRequest(entity))
                    
                    # Update database
                    await self.db.update_channel_info(
                        channel_id,
                        title=entity.title,
                        description=getattr(full_channel.full_chat, 'about', ''),
                        member_count=getattr(full_channel.full_chat, 'participants_count', 0)
                    )
                    
                    # Store analytics
                    await self.db.store_analytics_data(
                        'channel', channel_id, 'member_count',
                        getattr(full_channel.full_chat, 'participants_count', 0),
                        {'event': 'auto_refresh', 'account_id': account['id']}
                    )
                    
                    # Update rate limiter
                    await self.bot_core.increment_rate_limit(account['id'])
                    
                    success = True
                    break
                    
                except FloodWaitError as e:
                    logger.warning(f"Rate limited for {e.seconds} seconds")
                    await asyncio.sleep(min(e.seconds, 300))  # Max 5 minute wait
                except ChannelPrivateError:
                    logger.warning(f"Channel {channel['channel_id']} became private")
                    # Mark channel as inactive
                    await self.db.execute_query(
                        "UPDATE telegram_channels SET is_active = FALSE WHERE id = $1",
                        channel_id
                    )
                    break
                except Exception as e:
                    logger.warning(f"Failed to refresh with account {account['id']}: {e}")
                    continue
            
            if not success:
                logger.warning(f"Failed to refresh channel {channel_id}")
                
        except Exception as e:
            logger.error(f"Error in refresh channel task: {e}")
    
    async def _process_validate_channel(self, task_data: Dict[str, Any]):
        """Process channel validation task"""
        try:
            channel_id = task_data['channel_id']
            account_id = task_data['account_id']
            
            channel = await self.db.get_channel_by_id(channel_id)
            if not channel:
                return
            
            client = await self.bot_core.get_client(account_id)
            if not client:
                return
            
            # Try to access the channel
            try:
                entity = await client.get_entity(channel['channel_id'])
                
                # Channel is accessible
                await self.db.log_system_event(
                    'INFO', 'channel_processor',
                    f'Channel validation successful: {channel["title"]}',
                    {'channel_id': channel_id, 'account_id': account_id}
                )
                
            except ChannelPrivateError:
                # Channel is no longer accessible
                await self.db.execute_query(
                    "UPDATE telegram_channels SET is_active = FALSE WHERE id = $1",
                    channel_id
                )
                
                await self.db.log_system_event(
                    'WARNING', 'channel_processor',
                    f'Channel became inaccessible: {channel["title"]}',
                    {'channel_id': channel_id, 'account_id': account_id}
                )
                
        except Exception as e:
            logger.error(f"Error in validate channel task: {e}")
    
    async def _process_update_analytics(self, task_data: Dict[str, Any]):
        """Process analytics update task"""
        try:
            channel_id = task_data['channel_id']
            metrics = task_data['metrics']
            
            # Store each metric
            for metric_name, metric_value in metrics.items():
                await self.db.store_analytics_data(
                    'channel', channel_id, metric_name, metric_value,
                    {'event': 'scheduled_update'}
                )
                
        except Exception as e:
            logger.error(f"Error in update analytics task: {e}")
    
    async def _process_batch_refresh(self, task_data: Dict[str, Any]):
        """Process batch refresh task"""
        try:
            user_id = task_data['user_id']
            
            # Get all user channels
            channels = await self.db.get_user_channels(user_id, active_only=True)
            
            # Queue individual refresh tasks for each channel
            for channel in channels:
                await self.queue_channel_refresh(channel['id'], priority=3)
                
            logger.info(f"Queued batch refresh for {len(channels)} channels")
            
        except Exception as e:
            logger.error(f"Error in batch refresh task: {e}")
    
    async def get_channel_statistics(self, channel_id: int, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive channel statistics"""
        try:
            # Get channel info
            channel = await self.db.get_channel_by_id(channel_id)
            if not channel:
                return {'error': 'Channel not found'}
            
            # Get analytics data
            analytics = await self.db.get_analytics_data(
                'channel', channel_id, limit=days * 24  # Assuming hourly data
            )
            
            # Get campaigns
            campaigns = await self.db.fetch_all(
                "SELECT * FROM view_boost_campaigns WHERE channel_id = $1 ORDER BY created_at DESC",
                channel_id
            )
            
            # Calculate statistics
            total_campaigns = len(campaigns)
            active_campaigns = len([c for c in campaigns if c['status'] == 'active'])
            completed_campaigns = len([c for c in campaigns if c['status'] == 'completed'])
            
            total_target_views = sum(c['target_views'] for c in campaigns)
            total_current_views = sum(c['current_views'] for c in campaigns)
            
            # Get member count trend
            member_analytics = [a for a in analytics if a['metric_name'] == 'member_count']
            member_trend = []
            if member_analytics:
                member_trend = sorted(member_analytics, key=lambda x: x['timestamp'])
            
            return {
                'channel_info': channel,
                'campaigns': {
                    'total': total_campaigns,
                    'active': active_campaigns,
                    'completed': completed_campaigns,
                    'success_rate': (completed_campaigns / total_campaigns * 100) if total_campaigns > 0 else 0
                },
                'views': {
                    'target_total': total_target_views,
                    'current_total': total_current_views,
                    'completion_rate': (total_current_views / total_target_views * 100) if total_target_views > 0 else 0
                },
                'member_trend': member_trend,
                'analytics_points': len(analytics)
            }
            
        except Exception as e:
            logger.error(f"Error getting channel statistics: {e}")
            return {'error': str(e)}
    
    async def cleanup_inactive_channels(self, days: int = 90) -> int:
        """Cleanup channels that haven't been active"""
        try:
            # Find channels with no recent activity
            cutoff_date = datetime.now() - timedelta(days=days)
            
            inactive_channels = await self.db.fetch_all(
                """
                SELECT c.id, c.title, c.user_id
                FROM telegram_channels c
                LEFT JOIN view_boost_campaigns vbc ON c.id = vbc.channel_id 
                    AND vbc.created_at > $1
                WHERE c.updated_at < $1 
                AND vbc.id IS NULL
                AND c.is_active = TRUE
                """,
                cutoff_date
            )
            
            cleaned_count = 0
            for channel in inactive_channels:
                # Mark as inactive instead of deleting
                await self.db.execute_query(
                    "UPDATE telegram_channels SET is_active = FALSE, updated_at = NOW() WHERE id = $1",
                    channel['id']
                )
                
                # Log cleanup
                await self.db.log_system_event(
                    'INFO', 'channel_processor',
                    f'Marked inactive channel: {channel["title"]}',
                    {'channel_id': channel['id'], 'user_id': channel['user_id']}
                )
                
                cleaned_count += 1
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error cleaning up inactive channels: {e}")
            return 0
    
    async def get_processing_stats(self) -> Dict[str, Any]:
        """Get processor statistics"""
        return {
            'running': self._running,
            'workers': len(self._workers),
            'queue_size': self._processing_queue.qsize(),
            'active_workers': len([w for w in self._workers if not w.done()])
        }
    
    async def shutdown(self):
        """Shutdown channel processor"""
        try:
            logger.info("⏹️ Shutting down channel processor...")
            
            self._running = False
            
            # Cancel all workers
            for worker in self._workers:
                worker.cancel()
            
            # Wait for workers to finish
            if self._workers:
                await asyncio.gather(*self._workers, return_exceptions=True)
            
            # Clear queue
            while not self._processing_queue.empty():
                try:
                    self._processing_queue.get_nowait()
                    self._processing_queue.task_done()
                except asyncio.QueueEmpty:
                    break
            
            logger.info("✅ Channel processor shut down")
            
        except Exception as e:
            logger.error(f"Error shutting down channel processor: {e}")
