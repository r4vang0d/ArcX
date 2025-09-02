"""
Unified Database Manager
Main database interface for all bot operations
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
import json

from core.config.config import Config
from .coordinator import DatabaseCoordinator

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Unified database manager for all bot operations"""
    
    def __init__(self):
        self.config = Config()
        self.coordinator = DatabaseCoordinator(self.config)
        self._initialized = False
        
    async def initialize(self):
        """Initialize database manager"""
        if self._initialized:
            return
        
        try:
            await self.coordinator.initialize()
            self._initialized = True
            logger.info("✅ Database manager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database manager: {e}")
            raise
    
    async def execute_query(self, query: str, *args) -> Any:
        """Execute a database query"""
        if not self._initialized:
            raise RuntimeError("Database manager not initialized")
        
        return await self.coordinator.execute_query(query, *args)
    
    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Fetch single row"""
        if not self._initialized:
            raise RuntimeError("Database manager not initialized")
        
        return await self.coordinator.fetch_one(query, *args)
    
    async def fetch_all(self, query: str, *args) -> List[Dict[str, Any]]:
        """Fetch all rows"""
        if not self._initialized:
            raise RuntimeError("Database manager not initialized")
        
        return await self.coordinator.fetch_all(query, *args)
    
    # User Management Operations
    async def create_user(self, user_id: int, username: str = None, first_name: str = None, 
                         last_name: str = None, is_admin: bool = False) -> bool:
        """Create or update user"""
        try:
            await self.execute_query(
                """
                INSERT INTO users (user_id, username, first_name, last_name, is_admin, first_seen, last_seen)
                VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
                ON CONFLICT (user_id) 
                DO UPDATE SET 
                    username = $2, 
                    first_name = $3, 
                    last_name = $4, 
                    last_seen = NOW(),
                    updated_at = NOW()
                """,
                user_id, username, first_name, last_name, is_admin
            )
            return True
        except Exception as e:
            logger.error(f"Failed to create/update user {user_id}: {e}")
            return False
    
    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        return await self.fetch_one(
            "SELECT * FROM users WHERE user_id = $1",
            user_id
        )
    
    async def get_all_users(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all users"""
        query = "SELECT * FROM users"
        if active_only:
            query += " WHERE is_active = TRUE"
        query += " ORDER BY created_at DESC"
        
        return await self.fetch_all(query)
    
    async def update_user_settings(self, user_id: int, settings: Dict[str, Any]) -> bool:
        """Update user settings"""
        try:
            await self.execute_query(
                "UPDATE users SET settings = $2, updated_at = NOW() WHERE user_id = $1",
                user_id, json.dumps(settings)
            )
            return True
        except Exception as e:
            logger.error(f"Failed to update user settings for {user_id}: {e}")
            return False
    
    # Telegram Account Management
    async def add_telegram_account(self, user_id: int, phone_number: str, 
                                  api_id: int, api_hash: str, unique_id: str = None) -> Optional[int]:
        """Add new Telegram account"""
        try:
            # Generate unique_id if not provided
            if unique_id is None:
                import uuid
                unique_id = str(uuid.uuid4())[:8]
                
            account_id = await self.execute_query(
                """
                INSERT INTO telegram_accounts (user_id, phone_number, api_id, api_hash, unique_id, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
                RETURNING id
                """,
                user_id, phone_number, api_id, api_hash, unique_id
            )
            return account_id
        except Exception as e:
            logger.error(f"Failed to add Telegram account {phone_number}: {e}")
            return None
    
    async def get_user_accounts(self, user_id: int, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get user's Telegram accounts"""
        query = "SELECT * FROM telegram_accounts WHERE user_id = $1"
        if active_only:
            query += " AND is_active = TRUE"
        query += " ORDER BY created_at DESC"
        
        return await self.fetch_all(query, user_id)
    
    async def get_account_by_id(self, account_id: int) -> Optional[Dict[str, Any]]:
        """Get account by ID"""
        return await self.fetch_one(
            "SELECT * FROM telegram_accounts WHERE id = $1",
            account_id
        )
    
    async def update_account_session(self, account_id: int, session_data: str) -> bool:
        """Update account session data"""
        try:
            await self.execute_query(
                """
                UPDATE telegram_accounts 
                SET session_data = $2, is_verified = TRUE, last_login = NOW(), updated_at = NOW() 
                WHERE id = $1
                """,
                account_id, session_data
            )
            return True
        except Exception as e:
            logger.error(f"Failed to update session for account {account_id}: {e}")
            return False
    
    async def deactivate_account(self, account_id: int) -> bool:
        """Deactivate Telegram account"""
        try:
            await self.execute_query(
                "UPDATE telegram_accounts SET is_active = FALSE, updated_at = NOW() WHERE id = $1",
                account_id
            )
            return True
        except Exception as e:
            logger.error(f"Failed to deactivate account {account_id}: {e}")
            return False
    
    # Channel Management
    async def add_channel(self, user_id: int, channel_id: int, username: str = None,
                         title: str = None, description: str = None) -> Optional[int]:
        """Add new channel"""
        try:
            db_channel_id = await self.execute_query(
                """
                INSERT INTO channels (user_id, channel_id, username, title, description, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
                ON CONFLICT (channel_id) 
                DO UPDATE SET 
                    username = $3, 
                    title = $4, 
                    description = $5,
                    updated_at = NOW()
                RETURNING id
                """,
                user_id, channel_id, username, title, description
            )
            return db_channel_id
        except Exception as e:
            logger.error(f"Failed to add channel {channel_id}: {e}")
            return None
    
    async def get_user_channels(self, user_id: int, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get user's channels"""
        query = "SELECT * FROM channels WHERE user_id = $1"
        if active_only:
            query += " AND is_active = TRUE"
        query += " ORDER BY created_at DESC"
        
        return await self.fetch_all(query, user_id)
    
    async def get_channel_by_id(self, channel_db_id: int) -> Optional[Dict[str, Any]]:
        """Get channel by database ID"""
        return await self.fetch_one(
            "SELECT * FROM channels WHERE id = $1",
            channel_db_id
        )
    
    async def get_channel_by_channel_id(self, channel_id: int) -> Optional[Dict[str, Any]]:
        """Get channel by Telegram channel ID"""
        return await self.fetch_one(
            "SELECT * FROM channels WHERE channel_id = $1",
            channel_id
        )
    
    async def update_channel_info(self, channel_db_id: int, title: str = None, 
                                 description: str = None, member_count: int = None) -> bool:
        """Update channel information"""
        try:
            updates = []
            params = []
            param_count = 1
            
            if title is not None:
                updates.append(f"title = ${param_count}")
                params.append(title)
                param_count += 1
            
            if description is not None:
                updates.append(f"description = ${param_count}")
                params.append(description)
                param_count += 1
            
            if member_count is not None:
                updates.append(f"member_count = ${param_count}")
                params.append(member_count)
                param_count += 1
            
            if not updates:
                return True
            
            updates.append(f"updated_at = NOW()")
            params.append(channel_db_id)
            
            query = f"UPDATE channels SET {', '.join(updates)} WHERE id = ${param_count}"
            
            await self.execute_query(query, *params)
            return True
        except Exception as e:
            logger.error(f"Failed to update channel {channel_db_id}: {e}")
            return False
    
    # View Boost Campaign Management
    async def create_view_boost_campaign(self, user_id: int, channel_db_id: int, 
                                       message_id: int, target_views: int,
                                       campaign_type: str = 'manual') -> Optional[int]:
        """Create new view boost campaign"""
        try:
            campaign_id = await self.execute_query(
                """
                INSERT INTO view_boost_campaigns 
                (user_id, channel_id, message_id, target_views, campaign_type, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
                RETURNING id
                """,
                user_id, channel_db_id, message_id, target_views, campaign_type
            )
            return campaign_id
        except Exception as e:
            logger.error(f"Failed to create view boost campaign: {e}")
            return None
    
    async def get_user_campaigns(self, user_id: int, status: str = None) -> List[Dict[str, Any]]:
        """Get user's view boost campaigns"""
        query = """
        SELECT vbc.*, c.title as channel_title, c.username as channel_username
        FROM view_boost_campaigns vbc
        JOIN channels c ON vbc.channel_id = c.id
        WHERE vbc.user_id = $1
        """
        params = [user_id]
        
        if status:
            query += " AND vbc.status = $2"
            params.append(status)
        
        query += " ORDER BY vbc.created_at DESC"
        
        return await self.fetch_all(query, *params)
    
    async def update_campaign_progress(self, campaign_id: int, current_views: int, 
                                     status: str = None) -> bool:
        """Update campaign progress"""
        try:
            updates = ["current_views = $2", "updated_at = NOW()"]
            params = [campaign_id, current_views]
            
            if status:
                updates.append("status = $3")
                params.append(status)
            
            query = f"UPDATE view_boost_campaigns SET {', '.join(updates)} WHERE id = $1"
            
            await self.execute_query(query, *params)
            return True
        except Exception as e:
            logger.error(f"Failed to update campaign progress {campaign_id}: {e}")
            return False
    
    async def log_view_boost(self, campaign_id: int, account_id: int, views_added: int,
                           success: bool, error_message: str = None) -> bool:
        """Log view boost operation"""
        try:
            await self.execute_query(
                """
                INSERT INTO view_boost_logs 
                (campaign_id, account_id, views_added, success, error_message, timestamp)
                VALUES ($1, $2, $3, $4, $5, NOW())
                """,
                campaign_id, account_id, views_added, success, error_message
            )
            return True
        except Exception as e:
            logger.error(f"Failed to log view boost: {e}")
            return False
    
    # Analytics Operations
    async def store_analytics_data(self, entity_type: str, entity_id: int, 
                                  metric_name: str, metric_value: float,
                                  metadata: Dict[str, Any] = None) -> bool:
        """Store analytics data"""
        try:
            await self.execute_query(
                """
                INSERT INTO analytics_data (entity_type, entity_id, metric_name, metric_value, metadata, timestamp)
                VALUES ($1, $2, $3, $4, $5, NOW())
                """,
                entity_type, entity_id, metric_name, metric_value, 
                json.dumps(metadata or {})
            )
            return True
        except Exception as e:
            logger.error(f"Failed to store analytics data: {e}")
            return False
    
    async def get_analytics_data(self, entity_type: str, entity_id: int = None,
                               metric_name: str = None, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get analytics data"""
        query = "SELECT * FROM analytics_data WHERE entity_type = $1"
        params = [entity_type]
        param_count = 2
        
        if entity_id is not None:
            query += f" AND entity_id = ${param_count}"
            params.append(entity_id)
            param_count += 1
        
        if metric_name:
            query += f" AND metric_name = ${param_count}"
            params.append(metric_name)
            param_count += 1
        
        query += f" ORDER BY timestamp DESC LIMIT ${param_count}"
        params.append(limit)
        
        return await self.fetch_all(query, *params)
    
    # System Operations
    async def log_system_event(self, log_level: str, module: str, message: str,
                             metadata: Dict[str, Any] = None) -> bool:
        """Log system event"""
        try:
            await self.execute_query(
                """
                INSERT INTO system_logs (log_level, module, message, metadata, timestamp)
                VALUES ($1, $2, $3, $4, NOW())
                """,
                log_level, module, message, json.dumps(metadata or {})
            )
            return True
        except Exception as e:
            logger.error(f"Failed to log system event: {e}")
            return False
    
    async def get_system_logs(self, log_level: str = None, module: str = None,
                            limit: int = 100) -> List[Dict[str, Any]]:
        """Get system logs"""
        query = "SELECT * FROM system_logs WHERE 1=1"
        params = []
        param_count = 1
        
        if log_level:
            query += f" AND log_level = ${param_count}"
            params.append(log_level)
            param_count += 1
        
        if module:
            query += f" AND module = ${param_count}"
            params.append(module)
            param_count += 1
        
        query += f" ORDER BY timestamp DESC LIMIT ${param_count}"
        params.append(limit)
        
        return await self.fetch_all(query, *params)
    
    async def cleanup_old_logs(self, days: int = None) -> int:
        """Cleanup old log entries"""
        if days is None:
            days = self.config.LOG_CLEANUP_DAYS
        
        try:
            deleted_count = await self.execute_query(
                "DELETE FROM system_logs WHERE timestamp < NOW() - INTERVAL '%s days' RETURNING COUNT(*)",
                days
            )
            return deleted_count or 0
        except Exception as e:
            logger.error(f"Failed to cleanup old logs: {e}")
            return 0
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get database health status"""
        try:
            coordinator_health = await self.coordinator.get_health_status()
            
            # Get table statistics
            table_stats = await self.fetch_all(
                """
                SELECT schemaname, relname as tablename, n_tup_ins, n_tup_upd, n_tup_del 
                FROM pg_stat_user_tables 
                WHERE schemaname = 'public'
                """
            )
            
            return {
                'coordinator': coordinator_health,
                'tables': table_stats,
                'initialized': self._initialized
            }
        except Exception as e:
            logger.error(f"Failed to get health status: {e}")
            return {'error': str(e)}
    
    async def close(self):
        """Close database manager"""
        try:
            if self.coordinator:
                await self.coordinator.close()
            self._initialized = False
            logger.info("✅ Database manager closed")
        except Exception as e:
            logger.error(f"Error closing database manager: {e}")
