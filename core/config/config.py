"""
Configuration Management and Database Override
Handles environment variables and forces external PostgreSQL usage
"""

import os
import sys
import logging
from typing import List, Optional
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class Config:
    """Configuration manager with mandatory external database override"""
    
    def __init__(self):
        """Initialize configuration and override Replit database"""
        self._load_environment_files()
        self._override_replit_database()
        self._validate_configuration()
        
    def _load_environment_files(self):
        """Load environment files in priority order"""
        # Load env file first (bot configuration)
        env_file = Path("env")
        if env_file.exists():
            load_dotenv(env_file)
            logger.info("✅ Loaded env configuration")
        else:
            logger.warning("⚠️ env file not found")
        
        # Load data.env file (external database - MANDATORY)
        data_env_file = Path("data.env")
        if data_env_file.exists():
            load_dotenv(data_env_file, override=True)
            logger.info("✅ Loaded data.env configuration")
        else:
            logger.error("❌ data.env file not found - External database required!")
            raise FileNotFoundError("data.env file is mandatory for external database")
    
    def _override_replit_database(self):
        """Force removal of Replit database variables and ensure external PostgreSQL"""
        # Remove Replit database environment variables
        replit_db_vars = [
            'REPLIT_DB_URL', 'REPLIT_DATABASE_URL', 'DATABASE_URL',
            'PGHOST', 'PGPORT', 'PGDATABASE', 'PGUSER', 'PGPASSWORD'
        ]
        
        for var in replit_db_vars:
            if var in os.environ:
                del os.environ[var]
                logger.info(f"🗑️ Removed Replit database variable: {var}")
        
        # Verify external database configuration
        required_db_vars = ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
        missing_vars = [var for var in required_db_vars if not os.getenv(var)]
        
        if missing_vars:
            logger.error(f"❌ Missing external database configuration: {missing_vars}")
            raise ValueError(f"External database configuration incomplete: {missing_vars}")
        
        logger.info("✅ External PostgreSQL configuration verified")
    
    def _validate_configuration(self):
        """Validate all required configuration values"""
        required_vars = {
            'BOT_TOKEN': 'Telegram bot token',
            'DEFAULT_API_ID': 'Telegram API ID', 
            'DEFAULT_API_HASH': 'Telegram API hash',
            'ADMIN_IDS': 'Admin user IDs'
        }
        
        missing_vars = []
        for var, description in required_vars.items():
            if not os.getenv(var):
                missing_vars.append(f"{var} ({description})")
        
        if missing_vars:
            logger.error(f"❌ Missing required configuration: {missing_vars}")
            raise ValueError(f"Required configuration missing: {missing_vars}")
        
        logger.info("✅ Configuration validation completed")
    
    # Bot Configuration
    @property
    def BOT_TOKEN(self) -> str:
        """Telegram bot token"""
        return os.getenv('BOT_TOKEN', '')
    
    @property
    def DEFAULT_API_ID(self) -> int:
        """Default Telegram API ID"""
        return int(os.getenv('DEFAULT_API_ID', '0'))
    
    @property
    def DEFAULT_API_HASH(self) -> str:
        """Default Telegram API hash"""
        return os.getenv('DEFAULT_API_HASH', '')
    
    @property
    def ADMIN_IDS(self) -> List[int]:
        """List of admin user IDs"""
        admin_ids_str = os.getenv('ADMIN_IDS', '')
        if not admin_ids_str:
            return []
        try:
            return [int(uid.strip()) for uid in admin_ids_str.split(',') if uid.strip()]
        except ValueError:
            logger.error("Invalid ADMIN_IDS format")
            return []
    
    # External Database Configuration (MANDATORY)
    @property
    def DB_HOST(self) -> str:
        """External PostgreSQL host"""
        return os.getenv('DB_HOST', '')
    
    @property
    def DB_PORT(self) -> int:
        """External PostgreSQL port"""
        return int(os.getenv('DB_PORT', '5432'))
    
    @property
    def DB_NAME(self) -> str:
        """External PostgreSQL database name"""
        return os.getenv('DB_NAME', '')
    
    @property
    def DB_USER(self) -> str:
        """External PostgreSQL username"""
        return os.getenv('DB_USER', '')
    
    @property
    def DB_PASSWORD(self) -> str:
        """External PostgreSQL password"""
        return os.getenv('DB_PASSWORD', '')
    
    @property
    def DATABASE_URL(self) -> str:
        """Complete external database URL"""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    # Performance Settings
    @property
    def MAX_ACTIVE_CLIENTS(self) -> int:
        """Maximum number of active Telegram clients"""
        return int(os.getenv('MAX_ACTIVE_CLIENTS', '100'))
    
    @property
    def DB_POOL_SIZE(self) -> int:
        """Database connection pool size"""
        return int(os.getenv('DB_POOL_SIZE', '5'))
    
    @property
    def DB_MAX_POOL_SIZE(self) -> int:
        """Maximum database connection pool size"""
        return int(os.getenv('DB_MAX_POOL_SIZE', '20'))
    
    @property
    def DB_TIMEOUT(self) -> int:
        """Database connection timeout"""
        return int(os.getenv('DB_TIMEOUT', '30'))
    
    # Rate Limiting
    @property
    def CALLS_PER_MINUTE_PER_ACCOUNT(self) -> int:
        """API calls per minute per account"""
        return int(os.getenv('CALLS_PER_MINUTE_PER_ACCOUNT', '20'))
    
    @property
    def CALLS_PER_HOUR_PER_ACCOUNT(self) -> int:
        """API calls per hour per account"""
        return int(os.getenv('CALLS_PER_HOUR_PER_ACCOUNT', '500'))
    
    # Processing Settings
    @property
    def BATCH_SIZE(self) -> int:
        """Batch processing size"""
        return int(os.getenv('BATCH_SIZE', '10'))
    
    @property
    def MAX_ACCOUNTS_PER_OPERATION(self) -> int:
        """Maximum accounts per operation"""
        return int(os.getenv('MAX_ACCOUNTS_PER_OPERATION', '50'))
    
    @property
    def DEFAULT_DELAY_MIN(self) -> int:
        """Minimum delay between operations (seconds)"""
        return int(os.getenv('DEFAULT_DELAY_MIN', '1'))
    
    @property
    def DEFAULT_DELAY_MAX(self) -> int:
        """Maximum delay between operations (seconds)"""
        return int(os.getenv('DEFAULT_DELAY_MAX', '5'))
    
    @property
    def MAX_RETRY_ATTEMPTS(self) -> int:
        """Maximum retry attempts for failed operations"""
        return int(os.getenv('MAX_RETRY_ATTEMPTS', '3'))
    
    # Session Management
    @property
    def SESSION_DIR(self) -> str:
        """Directory for session files"""
        return os.getenv('SESSION_DIR', 'sessions')
    
    @property
    def SESSION_TIMEOUT(self) -> int:
        """Session timeout in seconds"""
        return int(os.getenv('SESSION_TIMEOUT', '3600'))
    
    # Resource Management
    @property
    def LOG_CLEANUP_DAYS(self) -> int:
        """Days to keep log files"""
        return int(os.getenv('LOG_CLEANUP_DAYS', '30'))
    
    # Monitoring Settings
    @property
    def HEALTH_CHECK_INTERVAL(self) -> int:
        """Health check interval in seconds"""
        return int(os.getenv('HEALTH_CHECK_INTERVAL', '300'))
    
    @property
    def PERFORMANCE_LOG_INTERVAL(self) -> int:
        """Performance logging interval in seconds"""
        return int(os.getenv('PERFORMANCE_LOG_INTERVAL', '600'))
    
    # Feature-specific Settings
    @property
    def AUTO_JOIN_DELAY_MIN(self) -> int:
        """Minimum delay for auto-joining live streams"""
        return int(os.getenv('AUTO_JOIN_DELAY_MIN', '5'))
    
    @property
    def AUTO_JOIN_DELAY_MAX(self) -> int:
        """Maximum delay for auto-joining live streams"""
        return int(os.getenv('AUTO_JOIN_DELAY_MAX', '15'))
    
    @property
    def VIEW_BOOST_DELAY_MIN(self) -> int:
        """Minimum delay for view boosting"""
        return int(os.getenv('VIEW_BOOST_DELAY_MIN', '2'))
    
    @property
    def VIEW_BOOST_DELAY_MAX(self) -> int:
        """Maximum delay for view boosting"""
        return int(os.getenv('VIEW_BOOST_DELAY_MAX', '8'))
    
    @property
    def MAX_VIEWS_PER_ACCOUNT_DAILY(self) -> int:
        """Maximum views per account per day"""
        return int(os.getenv('MAX_VIEWS_PER_ACCOUNT_DAILY', '1000'))
    
    @property
    def REACTION_DELAY_MIN(self) -> int:
        """Minimum delay for emoji reactions"""
        return int(os.getenv('REACTION_DELAY_MIN', '3'))
    
    @property
    def REACTION_DELAY_MAX(self) -> int:
        """Maximum delay for emoji reactions"""
        return int(os.getenv('REACTION_DELAY_MAX', '10'))
    
    @property
    def MAX_REACTIONS_PER_ACCOUNT_DAILY(self) -> int:
        """Maximum reactions per account per day"""
        return int(os.getenv('MAX_REACTIONS_PER_ACCOUNT_DAILY', '500'))
    
    def get_database_config(self) -> dict:
        """Get database configuration dictionary"""
        return {
            'host': self.DB_HOST,
            'port': self.DB_PORT,
            'database': self.DB_NAME,
            'user': self.DB_USER,
            'password': self.DB_PASSWORD,
            'min_size': self.DB_POOL_SIZE,
            'max_size': self.DB_MAX_POOL_SIZE,
            'command_timeout': self.DB_TIMEOUT
        }
    
    def validate_telegram_config(self) -> bool:
        """Validate Telegram API configuration"""
        return bool(
            self.BOT_TOKEN and 
            self.DEFAULT_API_ID and 
            self.DEFAULT_API_HASH and 
            self.ADMIN_IDS
        )
    
    def __str__(self) -> str:
        """String representation of configuration (safe for logging)"""
        return f"Config(db_host={self.DB_HOST}, api_id={self.DEFAULT_API_ID}, admins={len(self.ADMIN_IDS)})"
