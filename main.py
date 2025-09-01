#!/usr/bin/env python3
"""
Telegram Channel Management Bot - Main Entry Point
Comprehensive bot for channel management, view boosting, and live stream operations
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.config.config import Config
from core.database.unified_database import DatabaseManager
from telegram_bot import TelegramBot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


async def main():
    """Main application entry point"""
    try:
        logger.info("🚀 Starting Telegram Channel Management Bot...")
        
        # Initialize configuration
        config = Config()
        logger.info("✅ Configuration loaded successfully")
        
        # Initialize database
        db_manager = DatabaseManager()
        await db_manager.initialize()
        logger.info("✅ Database initialized successfully")
        
        # Initialize and start the bot
        bot = TelegramBot(config, db_manager)
        await bot.initialize()
        logger.info("✅ Bot initialized successfully")
        
        # Start the bot
        logger.info("🎯 Bot is running and ready to serve!")
        await bot.start()
        
    except KeyboardInterrupt:
        logger.info("⏹️ Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Cleanup resources
        try:
            if 'db_manager' in locals():
                await db_manager.close()
            if 'bot' in locals():
                await bot.shutdown()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


if __name__ == "__main__":
    # Set event loop policy for Windows compatibility
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Run the bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        sys.exit(1)
