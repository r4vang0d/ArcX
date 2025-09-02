# Telegram Channel Management Bot

A comprehensive Telegram bot for channel management, view boosting, and live stream automation using Python, aiogram, and Telethon.

## 🔥 CRITICAL DATABASE RULES - READ FIRST! 🔥

**MANDATORY RULE BOOK FOR ALL AGENTS:**

1. **🚨 NEVER USE REPLIT DATABASE** - This project MUST use external telethon_db only
2. **✅ ALWAYS USE TELETHON_DB** - Located at 18.234.56.13, database name: telethon_db
3. **⚠️ DELETE ANY REPLIT DATABASE** - If created accidentally, delete it immediately
4. **📋 DATABASE CONFIG SOURCE** - All database settings come from `data.env` file ONLY
5. **🔒 NO EXCEPTIONS** - External telethon_db is the ONLY allowed database

### Database Configuration:
- **Host:** 18.234.56.13 (from data.env)
- **Database:** telethon_db (from data.env) 
- **User:** arcx (from data.env)
- **Port:** 5432 (from data.env)
- **Password:** From data.env file

### What to do if Replit database exists:
1. Delete it immediately
2. Restart the bot workflow
3. Verify logs show connection to 18.234.56.13/telethon_db
4. Never create or provision Replit databases

## 🚀 Features

### Core Features
- **Channel Management** - Add, configure, and manage multiple Telegram channels with universal link support
- **View Boosting** - Automatic and manual view boosting with intelligent scheduling and rate limiting
- **Live Stream Management** - Auto-join live streams and voice chats with monitoring capabilities
- **Multi-Account Support** - Manage up to 100 Telegram accounts simultaneously with session recovery
- **Emoji Reactions** - Automated emoji reactions with smart patterns and timing
- **Real-time Analytics** - Comprehensive performance monitoring and reporting with export capabilities
- **System Health** - Bot performance, database health, and resource monitoring with alerts

### Advanced Features
- **Smart Rate Limiting** - Intelligent API throttling to prevent flood errors
- **Session Recovery** - Automatic recovery of orphaned session files
- **Circuit Breakers** - Prevent cascade failures with automatic recovery
- **Performance Monitoring** - Real-time system metrics and optimization
- **Request Batching** - Optimize API calls through intelligent batching
- **Caching Layer** - High-performance caching for faster responses
- **Account Rotation** - Smart rotation of accounts to avoid detection

### Technical Features
- **External PostgreSQL** - Mandatory external database integration with connection pooling
- **Async Architecture** - Full async/await implementation for high performance
- **Modular Design** - Clean separation with feature-based modules
- **Comprehensive Logging** - Detailed logging with structured format
- **Error Recovery** - Robust error handling and automatic recovery
- **Resource Management** - Automatic cleanup and optimization

## 🏗️ Architecture

### Core Components

#### Main Entry Point
- **`main.py`** - Application entry point with initialization sequence
- **`telegram_bot.py`** - Main bot controller and feature coordination

#### Core System (`core/`)
- **`config/config.py`** - Configuration management with database override
- **`database/`**
  - `unified_database.py` - Main database interface
  - `coordinator.py` - Connection pooling and schema management
  - `universal_access.py` - High-level database operations
- **`bot/telegram_bot.py`** - Telegram client management and session handling
- **`utils/`**
  - `performance_monitor.py` - Real-time performance tracking
  - `cache_manager.py` - High-performance caching system
  - `circuit_breaker.py` - API reliability and failure prevention
  - `request_batcher.py` - API call optimization
  - `http_client.py` - HTTP client utilities

#### Feature Modules (`features/`)

##### Channel Management
- **`handler.py`** - Main channel management logic
- **`keyboards.py`** - UI keyboard layouts
- **`utils.py`** - Channel validation and processing
- **`core/channel_processor.py`** - Channel data processing
- **`handlers/`** - Specialized handlers for add/list operations

##### View Manager
- **`handler.py`** - View boosting coordination
- **`handlers/auto_boost.py`** - Automatic view boosting engine
- **`handlers/manual_boost.py`** - Manual boost operations
- **`utils/scheduler.py`** - Campaign scheduling system
- **`utils/time_parse.py`** - Time parsing utilities

##### Account Management
- **`handler.py`** - Telegram account management with API support

##### Analytics
- **`handler.py`** - Comprehensive analytics and reporting system

##### Emoji Reactions
- **`handler.py`** - Automated emoji reaction system with pattern intelligence

##### Live Management
- **`handler.py`** - Live stream monitoring and auto-join functionality
- **`keyboards.py`** - Live management UI components
- **`states.py`** - FSM states for live operations
- **`utils.py`** - Live stream utilities

##### System Health
- **`handler.py`** - System monitoring and health checks

#### Central Routing
- **`inline_handler.py`** - Central callback router for all features

### Database Schema

The bot uses PostgreSQL with the following key tables:
- **users** - User profiles and admin settings
- **telegram_accounts** - Telegram account sessions and credentials
- **channels** - Channel information and configuration
- **view_boost_campaigns** - View boosting campaigns and progress
- **emoji_reactions** - Emoji reaction configurations and history
- **live_stream_participants** - Live stream participation tracking
- **analytics_data** - Performance metrics and analytics
- **system_logs** - System events and error logging

### File Structure

```
telegram-channel-management-bot/
├── main.py                          # Application entry point
├── telegram_bot.py                  # Main bot controller
├── inline_handler.py               # Central callback router
├── pyproject.toml                  # Project configuration & dependencies
├── env                             # Bot tokens and API credentials  
├── data.env                        # External database configuration
├── sessions/                       # Telegram session files
│   └── account_1.session          # Account session data
├── core/                           # Core system components
│   ├── config/
│   │   └── config.py              # Configuration manager
│   ├── database/
│   │   ├── unified_database.py    # Main database interface
│   │   ├── coordinator.py         # Connection pooling
│   │   └── universal_access.py    # High-level operations
│   ├── bot/
│   │   └── telegram_bot.py        # Client session management
│   └── utils/
│       ├── performance_monitor.py  # System metrics
│       ├── cache_manager.py       # Caching layer
│       ├── circuit_breaker.py     # API reliability
│       ├── request_batcher.py     # Request optimization
│       └── http_client.py         # HTTP utilities
└── features/                       # Feature modules
    ├── channel_management/
    │   ├── handler.py             # Channel operations
    │   ├── keyboards.py           # UI components
    │   ├── utils.py               # Channel validation
    │   ├── core/
    │   │   └── channel_processor.py
    │   └── handlers/
    │       ├── add_channel.py
    │       └── list_channels.py
    ├── view_manager/
    │   ├── handler.py             # View boost coordination
    │   ├── handlers/
    │   │   ├── auto_boost.py      # Auto boost engine
    │   │   └── manual_boost.py    # Manual operations
    │   └── utils/
    │       ├── scheduler.py       # Campaign scheduling
    │       └── time_parse.py      # Time utilities
    ├── account_management/
    │   └── handler.py             # Account management
    ├── analytics/
    │   └── handler.py             # Analytics & reporting
    ├── emoji_reactions/
    │   └── handler.py             # Emoji automation
    ├── live_management/
    │   ├── handler.py             # Live stream management
    │   ├── keyboards.py           # Live UI components
    │   ├── states.py              # FSM states
    │   └── utils.py               # Live utilities
    └── system_health/
        └── handler.py             # Health monitoring
```

## 🔧 Technical Implementation

### Dependencies (pyproject.toml)
- **aiogram 3.22.0+** - Modern Telegram Bot framework
- **telethon 1.40.0+** - Telegram client library for advanced operations
- **asyncpg 0.29.0+** - High-performance async PostgreSQL driver
- **psycopg2-binary 2.9.10+** - PostgreSQL adapter
- **python-dotenv 1.1.1+** - Environment variable management
- **psutil 7.0.0+** - System monitoring
- **pytz 2025.2** - Timezone handling
- **py-tgcalls 2.2.6+** - Voice call handling
- **aiofiles 24.1.0+** - Async file operations
- **cryptography 42.0.0+** - Cryptographic operations
- **pydantic 2.5.0+** - Data validation
- **httpx 0.26.0+** - HTTP client for API calls

### Configuration Files

#### Environment Variables (`env`)
- BOT_TOKEN - Telegram bot token
- DEFAULT_API_ID - Telegram API ID
- DEFAULT_API_HASH - Telegram API hash
- ADMIN_IDS - Comma-separated admin user IDs

#### Database Configuration (`data.env`)
- DB_HOST=18.234.56.13 - External PostgreSQL host
- DB_NAME=telethon_db - Database name
- DB_USER=arcx - Database user
- DB_PASSWORD - Database password
- Performance optimization settings for pools, timeouts, and rate limits

### Performance Optimizations

#### Rate Limiting
- 30 calls per minute per account (optimized from 20)
- 750 calls per hour per account (optimized from 500)
- Intelligent throttling to prevent API floods

#### Database Optimizations
- Connection pooling (10-50 connections)
- Async query execution
- Schema optimization with proper indexes
- Connection health monitoring

#### Request Optimization
- Request batching for efficiency
- Circuit breakers for reliability
- Smart caching layer (5-minute TTL)
- HTTP/2 support with keepalive

#### System Performance
- Reduced delays (0.5-2s vs 1-5s default)
- Parallel handler initialization
- Async task management
- Resource cleanup automation

## 🚨 Current Status

### Active Features
- Channel management with universal link support ✅
- Account management with session recovery ✅  
- View boosting with auto/manual modes ✅
- Analytics with comprehensive reporting ✅
- Emoji reactions with smart patterns ✅
- Live stream monitoring and auto-join ✅
- System health monitoring ✅

### Known Issues (from logs)
- Missing 'lm_select_channels' callback handler in live management
- Some callback routing warnings in inline_handler.py

### Performance Metrics
- Bot startup time: ~20-30 seconds
- Database connection: External PostgreSQL at 18.234.56.13
- Active workflow: "Telegram Bot Server" running on port 5000
- Session files: 1 active account session

## 🔄 Recent Changes (Last Updated: September 2, 2025)

### Architecture Improvements
- Implemented central inline callback routing system
- Added comprehensive database schema with proper relationships
- Enhanced error handling and logging throughout all modules
- Implemented performance monitoring and optimization layers

### Feature Enhancements  
- Channel management with universal link parsing
- Advanced view boosting with scheduling capabilities
- Live stream auto-join with intelligent monitoring
- Comprehensive analytics with export functionality
- Smart emoji reaction system with natural patterns

### Performance Optimizations
- Reduced API call delays for faster operations
- Implemented connection pooling for database efficiency
- Added caching layer for frequently accessed data
- Enhanced rate limiting to maximize API usage

## 👤 User Preferences

### Development Style
- Modular architecture with clear separation of concerns
- Comprehensive logging with emoji indicators for easy debugging
- Async/await patterns throughout for performance
- Type hints and validation using Pydantic
- External database integration (mandatory requirement)

### Code Conventions
- Snake_case for functions and variables
- PascalCase for classes
- Descriptive docstrings for all modules
- Structured error handling with specific exceptions
- Performance-focused implementation with monitoring
