"""
Database Coordinator
Manages database operations coordination and connection pooling
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import asyncpg
from contextlib import asynccontextmanager

from core.config.config import Config

logger = logging.getLogger(__name__)


class DatabaseCoordinator:
    """Coordinates database operations and manages connection pools"""
    
    def __init__(self, config: Config):
        self.config = config
        self.pool: Optional[asyncpg.Pool] = None
        self.connection_stats = {
            'total_connections': 0,
            'active_connections': 0,
            'failed_connections': 0,
            'last_health_check': None
        }
        self._health_check_task: Optional[asyncio.Task] = None
        
    async def initialize(self):
        """Initialize database connection pool"""
        try:
            logger.info("🔗 Initializing database connection pool...")
            logger.info(f"📍 Connecting to external database:")
            logger.info(f"   Host: {self.config.DB_HOST}")
            logger.info(f"   Port: {self.config.DB_PORT}")
            logger.info(f"   Database: {self.config.DB_NAME}")
            logger.info(f"   User: {self.config.DB_USER}")
            
            # Create connection pool
            self.pool = await asyncpg.create_pool(
                host=self.config.DB_HOST,
                port=self.config.DB_PORT,
                database=self.config.DB_NAME,
                user=self.config.DB_USER,
                password=self.config.DB_PASSWORD,
                min_size=self.config.DB_POOL_SIZE,
                max_size=self.config.DB_MAX_POOL_SIZE,
                command_timeout=self.config.DB_TIMEOUT,
                server_settings={
                    'application_name': 'telegram_channel_bot',
                    'timezone': 'UTC'
                }
            )
            
            # Test connection
            logger.info("🔍 Testing database connection...")
            await self._test_connection()
            
            # Initialize database schema
            logger.info("🛠️ Initializing database schema...")
            await self._initialize_schema()
            
            # Start health monitoring
            logger.info("💓 Starting health monitoring...")
            self._start_health_monitoring()
            
            logger.info("✅ Database coordinator initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize database coordinator: {e}")
            raise
    
    async def _test_connection(self):
        """Test database connection"""
        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                if result == 1:
                    logger.info("✅ Database connection test successful")
                    # Also test which database we're connected to
                    db_name = await conn.fetchval("SELECT current_database()")
                    logger.info(f"✅ Connected to database: {db_name}")
                else:
                    raise Exception("Database connection test failed")
        except Exception as e:
            logger.error(f"❌ Database connection test failed: {e}")
            raise
    
    async def _clear_existing_schema(self):
        """Clear existing schema (tables and indexes)"""
        try:
            logger.info("🗑️ Clearing existing database schema...")
            
            async with self.pool.acquire() as conn:
                # Drop tables in reverse dependency order
                drop_queries = [
                    "DROP TABLE IF EXISTS system_logs CASCADE",
                    "DROP TABLE IF EXISTS analytics_data CASCADE", 
                    "DROP TABLE IF EXISTS emoji_reactions CASCADE",
                    "DROP TABLE IF EXISTS live_stream_participants CASCADE",
                    "DROP TABLE IF EXISTS view_boost_campaigns CASCADE",
                    "DROP TABLE IF EXISTS channels CASCADE",
                    "DROP TABLE IF EXISTS telegram_accounts CASCADE",
                    "DROP TABLE IF EXISTS users CASCADE"
                ]
                
                for query in drop_queries:
                    await conn.execute(query)
                    logger.info(f"🗑️ Dropped table: {query.split()[4]}")
                
                logger.info("✅ Existing schema cleared successfully")
                
        except Exception as e:
            logger.error(f"❌ Failed to clear existing schema: {e}")
            raise

    async def _initialize_schema(self):
        """Initialize database schema"""
        try:
            logger.info("🔧 Starting database schema initialization...")
            
            # First check if we can access the database
            async with self.pool.acquire() as conn:
                db_name = await conn.fetchval("SELECT current_database()")
                logger.info(f"📋 Creating schema in database: {db_name}")
            
            # Clear existing schema first
            await self._clear_existing_schema()
            
            schema_queries = [
                # Users table
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    is_admin BOOLEAN DEFAULT FALSE,
                    is_active BOOLEAN DEFAULT TRUE,
                    first_seen TIMESTAMP DEFAULT NOW(),
                    last_seen TIMESTAMP DEFAULT NOW(),
                    settings JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
                """,
                
                # Telegram accounts table
                """
                CREATE TABLE IF NOT EXISTS telegram_accounts (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    phone_number VARCHAR(20) UNIQUE NOT NULL,
                    username VARCHAR(255),
                    api_id INTEGER NOT NULL,
                    api_hash VARCHAR(255) NOT NULL,
                    unique_id VARCHAR(255) UNIQUE,
                    session_data TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    is_verified BOOLEAN DEFAULT FALSE,
                    last_login TIMESTAMP,
                    rate_limit_data JSONB DEFAULT '{}',
                    settings JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
                """,
                
                # Channels table
                """
                CREATE TABLE IF NOT EXISTS telegram_channels (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    channel_id BIGINT UNIQUE NOT NULL,
                    username VARCHAR(255),
                    title VARCHAR(255),
                    description TEXT,
                    unique_id VARCHAR(255) UNIQUE,
                    member_count INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT TRUE,
                    settings JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
                """,
                
                # View boost campaigns table
                """
                CREATE TABLE IF NOT EXISTS view_boost_campaigns (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    channel_id INTEGER REFERENCES telegram_channels(id),
                    message_id BIGINT NOT NULL,
                    target_views INTEGER NOT NULL,
                    current_views INTEGER DEFAULT 0,
                    status VARCHAR(50) DEFAULT 'pending',
                    campaign_type VARCHAR(50) DEFAULT 'manual',
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    settings JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
                """,
                
                # View boost logs table
                """
                CREATE TABLE IF NOT EXISTS view_boost_logs (
                    id SERIAL PRIMARY KEY,
                    campaign_id INTEGER REFERENCES view_boost_campaigns(id),
                    account_id INTEGER REFERENCES telegram_accounts(id),
                    views_added INTEGER NOT NULL,
                    success BOOLEAN NOT NULL,
                    error_message TEXT,
                    timestamp TIMESTAMP DEFAULT NOW()
                )
                """,
                
                # Live streams table
                """
                CREATE TABLE IF NOT EXISTS live_streams (
                    id SERIAL PRIMARY KEY,
                    channel_id INTEGER REFERENCES telegram_channels(id),
                    stream_id BIGINT NOT NULL,
                    title VARCHAR(255),
                    is_active BOOLEAN DEFAULT TRUE,
                    participant_count INTEGER DEFAULT 0,
                    auto_join_enabled BOOLEAN DEFAULT FALSE,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    settings JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
                """,
                
                # Live stream participants table
                """
                CREATE TABLE IF NOT EXISTS live_stream_participants (
                    id SERIAL PRIMARY KEY,
                    stream_id INTEGER REFERENCES live_streams(id),
                    account_id INTEGER REFERENCES telegram_accounts(id),
                    joined_at TIMESTAMP DEFAULT NOW(),
                    left_at TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE
                )
                """,
                
                # Emoji reactions table
                """
                CREATE TABLE IF NOT EXISTS emoji_reactions (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    channel_id INTEGER REFERENCES telegram_channels(id),
                    message_id BIGINT NOT NULL,
                    emoji VARCHAR(50) NOT NULL,
                    reaction_count INTEGER DEFAULT 0,
                    auto_react_enabled BOOLEAN DEFAULT FALSE,
                    settings JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
                """,
                
                # Analytics data table
                """
                CREATE TABLE IF NOT EXISTS analytics_data (
                    id SERIAL PRIMARY KEY,
                    entity_type VARCHAR(50) NOT NULL,
                    entity_id INTEGER NOT NULL,
                    metric_name VARCHAR(100) NOT NULL,
                    metric_value NUMERIC NOT NULL,
                    metadata JSONB DEFAULT '{}',
                    timestamp TIMESTAMP DEFAULT NOW()
                )
                """,
                
                # System logs table
                """
                CREATE TABLE IF NOT EXISTS system_logs (
                    id SERIAL PRIMARY KEY,
                    log_level VARCHAR(20) NOT NULL,
                    module VARCHAR(100) NOT NULL,
                    message TEXT NOT NULL,
                    metadata JSONB DEFAULT '{}',
                    timestamp TIMESTAMP DEFAULT NOW()
                )
                """,
                
                # Create indexes separately (PostgreSQL syntax)
                """
                CREATE INDEX IF NOT EXISTS idx_analytics_entity ON analytics_data (entity_type, entity_id)
                """,
                """
                CREATE INDEX IF NOT EXISTS idx_analytics_metric ON analytics_data (metric_name)
                """,
                """
                CREATE INDEX IF NOT EXISTS idx_analytics_timestamp ON analytics_data (timestamp)
                """,
                """
                CREATE INDEX IF NOT EXISTS idx_logs_level ON system_logs (log_level)
                """,
                """
                CREATE INDEX IF NOT EXISTS idx_logs_module ON system_logs (module)
                """,
                """
                CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON system_logs (timestamp)
                """
            ]
            
            async with self.pool.acquire() as conn:
                for i, query in enumerate(schema_queries):
                    try:
                        await conn.execute(query)
                        logger.info(f"✅ Created schema component {i+1}/{len(schema_queries)}")
                    except Exception as query_error:
                        logger.error(f"❌ Failed to create schema component {i+1}: {query_error}")
                        logger.error(f"Query: {query[:100]}...")
                        raise
            
            logger.info("✅ Database schema initialized completely")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize database schema: {e}")
            raise
    
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection from pool"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        conn = None
        try:
            conn = await self.pool.acquire()
            self.connection_stats['active_connections'] += 1
            yield conn
        except Exception as e:
            self.connection_stats['failed_connections'] += 1
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                await self.pool.release(conn)
                self.connection_stats['active_connections'] -= 1
    
    async def execute_query(self, query: str, *args) -> Any:
        """Execute a database query"""
        try:
            async with self.get_connection() as conn:
                return await conn.fetchval(query, *args)
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    async def execute_many(self, query: str, args_list: List[tuple]) -> None:
        """Execute query with multiple parameter sets"""
        try:
            async with self.get_connection() as conn:
                await conn.executemany(query, args_list)
        except Exception as e:
            logger.error(f"Batch query execution failed: {e}")
            raise
    
    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Fetch single row"""
        try:
            async with self.get_connection() as conn:
                row = await conn.fetchrow(query, *args)
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Fetch one failed: {e}")
            raise
    
    async def fetch_all(self, query: str, *args) -> List[Dict[str, Any]]:
        """Fetch all rows"""
        try:
            async with self.get_connection() as conn:
                rows = await conn.fetch(query, *args)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Fetch all failed: {e}")
            raise
    
    def _start_health_monitoring(self):
        """Start background health monitoring"""
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("✅ Database health monitoring started")
    
    async def _health_check_loop(self):
        """Background health check loop"""
        while True:
            try:
                await asyncio.sleep(self.config.HEALTH_CHECK_INTERVAL)
                await self._perform_health_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    async def _perform_health_check(self):
        """Perform database health check"""
        try:
            start_time = datetime.now()
            
            # Test connection
            async with self.get_connection() as conn:
                await conn.fetchval("SELECT 1")
            
            # Update health check timestamp
            self.connection_stats['last_health_check'] = start_time
            
            # Log health metrics
            pool_size = self.pool.get_size() if self.pool else 0
            logger.debug(f"Database health check OK - Pool size: {pool_size}")
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get database health status"""
        if not self.pool:
            return {'status': 'disconnected', 'pool': None}
        
        return {
            'status': 'connected',
            'pool': {
                'size': self.pool.get_size(),
                'min_size': self.pool.get_min_size(),
                'max_size': self.pool.get_max_size(),
                'idle_connections': self.pool.get_idle_size()
            },
            'stats': self.connection_stats.copy(),
            'last_health_check': self.connection_stats['last_health_check']
        }
    
    async def close(self):
        """Close database connections and cleanup"""
        try:
            # Cancel health monitoring
            if self._health_check_task:
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass
            
            # Close connection pool
            if self.pool:
                await self.pool.close()
                logger.info("✅ Database connection pool closed")
            
        except Exception as e:
            logger.error(f"Error closing database coordinator: {e}")
