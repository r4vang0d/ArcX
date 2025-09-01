"""
Universal Database Access Layer
Provides high-level database operations for all features
"""

import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
import asyncio

from .unified_database import DatabaseManager

logger = logging.getLogger(__name__)


class UniversalDatabaseAccess:
    """Universal database access layer for all bot features"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        
    # User Operations
    async def ensure_user_exists(self, user_id: int, username: str = None, 
                               first_name: str = None, last_name: str = None,
                               is_admin: bool = False) -> Dict[str, Any]:
        """Ensure user exists in database and return user data"""
        await self.db.create_user(user_id, username, first_name, last_name, is_admin)
        return await self.db.get_user(user_id)
    
    async def get_user_with_settings(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user with parsed settings"""
        user = await self.db.get_user(user_id)
        if user and user.get('settings'):
            try:
                import json
                user['settings'] = json.loads(user['settings'])
            except:
                user['settings'] = {}
        return user
    
    async def update_user_last_seen(self, user_id: int) -> bool:
        """Update user's last seen timestamp"""
        return await self.db.execute_query(
            "UPDATE users SET last_seen = NOW(), updated_at = NOW() WHERE user_id = $1",
            user_id
        ) is not None
    
    # Channel Operations with Validation
    async def add_channel_safe(self, user_id: int, channel_id: int, username: str = None,
                              title: str = None, description: str = None) -> Dict[str, Any]:
        """Safely add channel with validation"""
        try:
            # Check if channel already exists
            existing = await self.db.get_channel_by_channel_id(channel_id)
            if existing:
                return {
                    'success': False, 
                    'error': 'Channel already exists',
                    'channel_id': existing['id']
                }
            
            # Add new channel
            db_channel_id = await self.db.add_channel(
                user_id, channel_id, username, title, description
            )
            
            if db_channel_id:
                return {
                    'success': True,
                    'channel_id': db_channel_id,
                    'message': 'Channel added successfully'
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to add channel'
                }
                
        except Exception as e:
            logger.error(f"Error adding channel safely: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_user_channels_with_stats(self, user_id: int) -> List[Dict[str, Any]]:
        """Get user channels with statistics"""
        channels = await self.db.get_user_channels(user_id)
        
        # Add statistics for each channel
        for channel in channels:
            # Get view boost campaign count
            campaigns = await self.db.fetch_all(
                "SELECT COUNT(*) as total, status FROM view_boost_campaigns WHERE channel_id = $1 GROUP BY status",
                channel['id']
            )
            
            channel['campaign_stats'] = {
                'total': sum(c['total'] for c in campaigns),
                'by_status': {c['status']: c['total'] for c in campaigns}
            }
            
            # Get recent analytics
            recent_views = await self.db.get_analytics_data(
                'channel', channel['id'], 'views', limit=7
            )
            channel['recent_views'] = recent_views
        
        return channels
    
    # Account Operations with Status Tracking
    async def add_account_with_validation(self, user_id: int, phone_number: str,
                                        api_id: int, api_hash: str) -> Dict[str, Any]:
        """Add account with validation and status tracking"""
        try:
            # Check account limit for user
            existing_accounts = await self.db.get_user_accounts(user_id)
            max_accounts = 10  # Configurable limit
            
            if len(existing_accounts) >= max_accounts:
                return {
                    'success': False,
                    'error': f'Maximum {max_accounts} accounts allowed per user'
                }
            
            # Add account
            account_id = await self.db.add_telegram_account(
                user_id, phone_number, api_id, api_hash
            )
            
            if account_id:
                # Log account creation
                await self.db.log_system_event(
                    'INFO', 'account_management', 
                    f'New account added: {phone_number}',
                    {'user_id': user_id, 'account_id': account_id}
                )
                
                return {
                    'success': True,
                    'account_id': account_id,
                    'message': 'Account added successfully'
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to add account'
                }
                
        except Exception as e:
            logger.error(f"Error adding account: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_accounts_with_health(self, user_id: int) -> List[Dict[str, Any]]:
        """Get accounts with health status"""
        accounts = await self.db.get_user_accounts(user_id)
        
        for account in accounts:
            # Calculate health score based on various factors
            health_score = 100
            health_issues = []
            
            # Check last login
            if account['last_login']:
                days_since_login = (datetime.now() - account['last_login']).days
                if days_since_login > 7:
                    health_score -= 20
                    health_issues.append(f'No login for {days_since_login} days')
            else:
                health_score -= 30
                health_issues.append('Never logged in')
            
            # Check verification status
            if not account['is_verified']:
                health_score -= 25
                health_issues.append('Not verified')
            
            # Check activity status
            if not account['is_active']:
                health_score = 0
                health_issues.append('Account deactivated')
            
            account['health_score'] = max(0, health_score)
            account['health_issues'] = health_issues
            account['health_status'] = 'good' if health_score >= 80 else 'warning' if health_score >= 50 else 'critical'
        
        return accounts
    
    # Campaign Operations with Progress Tracking
    async def create_campaign_with_tracking(self, user_id: int, channel_db_id: int,
                                          message_id: int, target_views: int,
                                          campaign_type: str = 'manual',
                                          settings: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create campaign with progress tracking setup"""
        try:
            campaign_id = await self.db.create_view_boost_campaign(
                user_id, channel_db_id, message_id, target_views, campaign_type
            )
            
            if campaign_id:
                # Store campaign settings
                if settings:
                    await self.db.execute_query(
                        "UPDATE view_boost_campaigns SET settings = $2 WHERE id = $1",
                        campaign_id, json.dumps(settings)
                    )
                
                # Log campaign creation
                await self.db.log_system_event(
                    'INFO', 'view_manager',
                    f'Campaign created: {campaign_id}',
                    {
                        'user_id': user_id,
                        'campaign_id': campaign_id,
                        'target_views': target_views,
                        'type': campaign_type
                    }
                )
                
                return {
                    'success': True,
                    'campaign_id': campaign_id,
                    'message': 'Campaign created successfully'
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to create campaign'
                }
                
        except Exception as e:
            logger.error(f"Error creating campaign: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_campaign_progress(self, campaign_id: int) -> Dict[str, Any]:
        """Get detailed campaign progress"""
        campaign = await self.db.fetch_one(
            """
            SELECT vbc.*, c.title as channel_title, c.username as channel_username
            FROM view_boost_campaigns vbc
            JOIN channels c ON vbc.channel_id = c.id
            WHERE vbc.id = $1
            """,
            campaign_id
        )
        
        if not campaign:
            return {'error': 'Campaign not found'}
        
        # Get boost logs
        logs = await self.db.fetch_all(
            """
            SELECT vbl.*, ta.phone_number
            FROM view_boost_logs vbl
            JOIN telegram_accounts ta ON vbl.account_id = ta.id
            WHERE vbl.campaign_id = $1
            ORDER BY vbl.timestamp DESC
            """,
            campaign_id
        )
        
        # Calculate statistics
        total_attempts = len(logs)
        successful_attempts = sum(1 for log in logs if log['success'])
        total_views_added = sum(log['views_added'] for log in logs if log['success'])
        
        progress_percentage = 0
        if campaign['target_views'] > 0:
            progress_percentage = min(100, (total_views_added / campaign['target_views']) * 100)
        
        return {
            'campaign': campaign,
            'logs': logs,
            'statistics': {
                'total_attempts': total_attempts,
                'successful_attempts': successful_attempts,
                'success_rate': (successful_attempts / total_attempts * 100) if total_attempts > 0 else 0,
                'total_views_added': total_views_added,
                'progress_percentage': progress_percentage,
                'remaining_views': max(0, campaign['target_views'] - total_views_added)
            }
        }
    
    # Analytics Operations
    async def get_user_analytics_summary(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive user analytics summary"""
        try:
            # Get user's channels
            channels = await self.db.get_user_channels(user_id)
            channel_ids = [c['id'] for c in channels]
            
            # Get campaigns summary
            campaigns = await self.db.get_user_campaigns(user_id)
            
            # Get recent analytics data
            analytics_data = {}
            for channel_id in channel_ids:
                channel_analytics = await self.db.get_analytics_data(
                    'channel', channel_id, limit=days
                )
                analytics_data[channel_id] = channel_analytics
            
            # Calculate summary statistics
            total_campaigns = len(campaigns)
            active_campaigns = len([c for c in campaigns if c['status'] == 'active'])
            completed_campaigns = len([c for c in campaigns if c['status'] == 'completed'])
            
            total_target_views = sum(c['target_views'] for c in campaigns)
            total_current_views = sum(c['current_views'] for c in campaigns)
            
            return {
                'channels': {
                    'total': len(channels),
                    'active': len([c for c in channels if c['is_active']]),
                    'details': channels
                },
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
                'analytics_data': analytics_data
            }
            
        except Exception as e:
            logger.error(f"Error getting user analytics: {e}")
            return {'error': str(e)}
    
    async def get_system_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive system health summary"""
        try:
            # Get database health
            db_health = await self.db.get_health_status()
            
            # Get user statistics
            total_users = len(await self.db.get_all_users(active_only=False))
            active_users = len(await self.db.get_all_users(active_only=True))
            
            # Get account statistics
            all_accounts = await self.db.fetch_all("SELECT * FROM telegram_accounts")
            active_accounts = [a for a in all_accounts if a['is_active']]
            verified_accounts = [a for a in all_accounts if a['is_verified']]
            
            # Get campaign statistics
            all_campaigns = await self.db.fetch_all("SELECT * FROM view_boost_campaigns")
            active_campaigns = [c for c in all_campaigns if c['status'] == 'active']
            
            # Get recent errors
            recent_errors = await self.db.get_system_logs('ERROR', limit=10)
            
            return {
                'database': db_health,
                'users': {
                    'total': total_users,
                    'active': active_users,
                    'activity_rate': (active_users / total_users * 100) if total_users > 0 else 0
                },
                'accounts': {
                    'total': len(all_accounts),
                    'active': len(active_accounts),
                    'verified': len(verified_accounts),
                    'verification_rate': (len(verified_accounts) / len(all_accounts) * 100) if all_accounts else 0
                },
                'campaigns': {
                    'total': len(all_campaigns),
                    'active': len(active_campaigns)
                },
                'recent_errors': recent_errors,
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return {'error': str(e)}
    
    # Batch Operations
    async def batch_update_analytics(self, analytics_batch: List[Dict[str, Any]]) -> int:
        """Batch update analytics data"""
        try:
            successful_updates = 0
            
            for item in analytics_batch:
                success = await self.db.store_analytics_data(
                    item['entity_type'],
                    item['entity_id'],
                    item['metric_name'],
                    item['metric_value'],
                    item.get('metadata')
                )
                if success:
                    successful_updates += 1
            
            return successful_updates
            
        except Exception as e:
            logger.error(f"Error in batch analytics update: {e}")
            return 0
    
    async def cleanup_old_data(self, days: int = None) -> Dict[str, int]:
        """Cleanup old data from various tables"""
        try:
            cleanup_results = {}
            
            # Cleanup logs
            logs_deleted = await self.db.cleanup_old_logs(days)
            cleanup_results['logs'] = logs_deleted
            
            # Cleanup old analytics data (keep last 90 days)
            analytics_days = days or 90
            analytics_deleted = await self.db.execute_query(
                "DELETE FROM analytics_data WHERE timestamp < NOW() - INTERVAL '%s days' RETURNING COUNT(*)",
                analytics_days
            )
            cleanup_results['analytics'] = analytics_deleted or 0
            
            # Cleanup old completed campaigns (keep last 30 days)
            campaigns_days = 30
            campaigns_deleted = await self.db.execute_query(
                """
                DELETE FROM view_boost_campaigns 
                WHERE status = 'completed' AND updated_at < NOW() - INTERVAL '%s days' 
                RETURNING COUNT(*)
                """,
                campaigns_days
            )
            cleanup_results['campaigns'] = campaigns_deleted or 0
            
            return cleanup_results
            
        except Exception as e:
            logger.error(f"Error in data cleanup: {e}")
            return {'error': str(e)}
