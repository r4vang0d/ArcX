"""
Boost Scheduler
Handles scheduling and timing for view boost campaigns
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import pytz

from core.config.config import Config
from core.database.unified_database import DatabaseManager

logger = logging.getLogger(__name__)


class BoostScheduler:
    """Handles scheduling of boost campaigns"""
    
    def __init__(self, db_manager: DatabaseManager, config: Config):
        self.db = db_manager
        self.config = config
        self._scheduler_task: Optional[asyncio.Task] = None
        self._running = False
        self._scheduled_campaigns: Dict[int, Dict[str, Any]] = {}
        
    async def initialize(self):
        """Initialize boost scheduler"""
        try:
            # Wait for database schema to be ready
            await asyncio.sleep(12)
            
            # Load existing scheduled campaigns
            await self._load_scheduled_campaigns()
            
            # Start scheduler task
            self._scheduler_task = asyncio.create_task(self._scheduler_loop())
            self._running = True
            
            logger.info("✅ Boost scheduler initialized")
        except Exception as e:
            logger.error(f"Failed to initialize boost scheduler: {e}")
            raise
    
    async def _load_scheduled_campaigns(self):
        """Load scheduled campaigns from database"""
        try:
            scheduled = await self.db.fetch_all(
                """
                SELECT id, start_time, settings
                FROM view_boost_campaigns
                WHERE start_time > NOW() AND status = 'scheduled'
                ORDER BY start_time ASC
                """
            )
            
            for campaign in scheduled:
                self._scheduled_campaigns[campaign['id']] = {
                    'start_time': campaign['start_time'],
                    'settings': campaign.get('settings', {})
                }
            
            logger.info(f"✅ Loaded {len(scheduled)} scheduled campaigns")
            
        except Exception as e:
            logger.error(f"Error loading scheduled campaigns: {e}")
    
    async def _scheduler_loop(self):
        """Main scheduler loop"""
        while self._running:
            try:
                current_time = datetime.now()
                
                # Check for campaigns to start
                campaigns_to_start = []
                for campaign_id, campaign_data in self._scheduled_campaigns.items():
                    if campaign_data['start_time'] <= current_time:
                        campaigns_to_start.append(campaign_id)
                
                # Start campaigns
                for campaign_id in campaigns_to_start:
                    try:
                        await self._start_scheduled_campaign(campaign_id)
                        del self._scheduled_campaigns[campaign_id]
                    except Exception as e:
                        logger.error(f"Error starting scheduled campaign {campaign_id}: {e}")
                
                # Sleep for a minute before next check
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(30)
    
    async def _start_scheduled_campaign(self, campaign_id: int):
        """Start a scheduled campaign"""
        try:
            # Update campaign status to active
            await self.db.update_campaign_progress(campaign_id, None, 'active')
            
            # Log the start
            await self.db.log_system_event(
                'INFO', 'boost_scheduler',
                f'Started scheduled campaign: {campaign_id}',
                {'campaign_id': campaign_id}
            )
            
            logger.info(f"✅ Started scheduled campaign {campaign_id}")
            
        except Exception as e:
            logger.error(f"Error starting scheduled campaign {campaign_id}: {e}")
            await self.db.update_campaign_progress(campaign_id, None, 'failed')
    
    async def schedule_campaign(self, campaign_id: int, start_time: datetime,
                              settings: Dict[str, Any] = None) -> bool:
        """Schedule a campaign for future execution"""
        try:
            # Update database
            await self.db.execute_query(
                "UPDATE view_boost_campaigns SET start_time = $2, status = 'scheduled', settings = $3 WHERE id = $1",
                campaign_id, start_time, settings or {}
            )
            
            # Add to internal scheduler
            self._scheduled_campaigns[campaign_id] = {
                'start_time': start_time,
                'settings': settings or {}
            }
            
            logger.info(f"✅ Scheduled campaign {campaign_id} for {start_time}")
            return True
            
        except Exception as e:
            logger.error(f"Error scheduling campaign {campaign_id}: {e}")
            return False
    
    async def cancel_scheduled_campaign(self, campaign_id: int) -> bool:
        """Cancel a scheduled campaign"""
        try:
            # Update database
            await self.db.update_campaign_progress(campaign_id, None, 'cancelled')
            
            # Remove from scheduler
            if campaign_id in self._scheduled_campaigns:
                del self._scheduled_campaigns[campaign_id]
            
            logger.info(f"✅ Cancelled scheduled campaign {campaign_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling scheduled campaign {campaign_id}: {e}")
            return False
    
    async def reschedule_campaign(self, campaign_id: int, new_start_time: datetime) -> bool:
        """Reschedule a campaign"""
        try:
            # Update database
            await self.db.execute_query(
                "UPDATE view_boost_campaigns SET start_time = $2 WHERE id = $1",
                campaign_id, new_start_time
            )
            
            # Update scheduler
            if campaign_id in self._scheduled_campaigns:
                self._scheduled_campaigns[campaign_id]['start_time'] = new_start_time
            
            logger.info(f"✅ Rescheduled campaign {campaign_id} to {new_start_time}")
            return True
            
        except Exception as e:
            logger.error(f"Error rescheduling campaign {campaign_id}: {e}")
            return False
    
    async def get_scheduled_campaigns(self, user_id: int = None) -> List[Dict[str, Any]]:
        """Get scheduled campaigns"""
        try:
            if user_id:
                campaigns = await self.db.fetch_all(
                    """
                    SELECT vbc.*, c.title as channel_title
                    FROM view_boost_campaigns vbc
                    JOIN telegram_channels c ON vbc.channel_id = c.id
                    WHERE vbc.user_id = $1 AND vbc.status = 'scheduled'
                    ORDER BY vbc.start_time ASC
                    """,
                    user_id
                )
            else:
                campaigns = await self.db.fetch_all(
                    """
                    SELECT vbc.*, c.title as channel_title
                    FROM view_boost_campaigns vbc
                    JOIN telegram_channels c ON vbc.channel_id = c.id
                    WHERE vbc.status = 'scheduled'
                    ORDER BY vbc.start_time ASC
                    """
                )
            
            return campaigns
            
        except Exception as e:
            logger.error(f"Error getting scheduled campaigns: {e}")
            return []
    
    async def get_optimal_boost_times(self, channel_id: int, days: int = 7) -> List[Dict[str, Any]]:
        """Get optimal boost times based on historical data"""
        try:
            # Get historical boost performance data
            performance_data = await self.db.fetch_all(
                """
                SELECT 
                    EXTRACT(hour FROM vbl.timestamp) as hour,
                    EXTRACT(dow FROM vbl.timestamp) as day_of_week,
                    AVG(vbl.views_added) as avg_views,
                    COUNT(*) as total_boosts,
                    SUM(CASE WHEN vbl.success THEN 1 ELSE 0 END) as successful_boosts
                FROM view_boost_logs vbl
                JOIN view_boost_campaigns vbc ON vbl.campaign_id = vbc.id
                WHERE vbc.channel_id = $1 
                AND vbl.timestamp >= NOW() - INTERVAL '%s days'
                GROUP BY hour, day_of_week
                HAVING COUNT(*) >= 5
                ORDER BY avg_views DESC, successful_boosts DESC
                LIMIT 10
                """,
                channel_id, days
            )
            
            optimal_times = []
            for data in performance_data:
                optimal_times.append({
                    'hour': int(data['hour']),
                    'day_of_week': int(data['day_of_week']),
                    'avg_views': float(data['avg_views']),
                    'success_rate': (data['successful_boosts'] / data['total_boosts']) * 100
                })
            
            return optimal_times
            
        except Exception as e:
            logger.error(f"Error getting optimal boost times: {e}")
            return []
    
    async def suggest_next_boost_time(self, timezone: str = 'UTC') -> datetime:
        """Suggest optimal time for next boost"""
        try:
            tz = pytz.timezone(timezone)
            now = datetime.now(tz)
            
            # Peak hours: typically 6-9 PM local time
            peak_hour = 19  # 7 PM
            
            # Calculate next peak time
            next_boost = now.replace(hour=peak_hour, minute=0, second=0, microsecond=0)
            
            # If past peak time today, schedule for tomorrow
            if now.hour >= peak_hour:
                next_boost += timedelta(days=1)
            
            return next_boost.replace(tzinfo=None)  # Remove timezone for database
            
        except Exception as e:
            logger.error(f"Error suggesting next boost time: {e}")
            # Fallback: next hour
            return datetime.now() + timedelta(hours=1)
    
    def parse_time_expression(self, time_expr: str) -> Optional[datetime]:
        """Parse human-readable time expressions"""
        try:
            time_expr = time_expr.lower().strip()
            now = datetime.now()
            
            # Handle common expressions
            if time_expr in ['now', 'immediately']:
                return now
            elif time_expr in ['in 1 hour', '1 hour', '+1h']:
                return now + timedelta(hours=1)
            elif time_expr in ['in 2 hours', '2 hours', '+2h']:
                return now + timedelta(hours=2)
            elif time_expr in ['tomorrow', 'next day']:
                return now.replace(hour=12, minute=0, second=0) + timedelta(days=1)
            elif time_expr.startswith('in ') and time_expr.endswith(' minutes'):
                minutes = int(time_expr.replace('in ', '').replace(' minutes', ''))
                return now + timedelta(minutes=minutes)
            elif time_expr.startswith('at '):
                # Handle "at 15:30" format
                time_part = time_expr.replace('at ', '')
                if ':' in time_part:
                    hour, minute = map(int, time_part.split(':'))
                    target_time = now.replace(hour=hour, minute=minute, second=0)
                    if target_time <= now:
                        target_time += timedelta(days=1)
                    return target_time
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing time expression: {e}")
            return None
    
    async def get_scheduler_status(self) -> Dict[str, Any]:
        """Get scheduler status and statistics"""
        try:
            return {
                'running': self._running,
                'scheduled_campaigns': len(self._scheduled_campaigns),
                'next_scheduled': min(
                    (data['start_time'] for data in self._scheduled_campaigns.values()),
                    default=None
                )
            }
            
        except Exception as e:
            logger.error(f"Error getting scheduler status: {e}")
            return {'running': False, 'scheduled_campaigns': 0, 'next_scheduled': None}
    
    async def shutdown(self):
        """Shutdown scheduler"""
        try:
            logger.info("⏹️ Shutting down boost scheduler...")
            
            self._running = False
            
            if self._scheduler_task:
                self._scheduler_task.cancel()
                try:
                    await self._scheduler_task
                except asyncio.CancelledError:
                    pass
            
            logger.info("✅ Boost scheduler shut down")
            
        except Exception as e:
            logger.error(f"Error shutting down scheduler: {e}")
