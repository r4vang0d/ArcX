"""
Telegram Bot Core
Core bot functionality and session management
"""

import asyncio
import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime

from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
from telethon.tl import types, functions

from core.config.config import Config
from core.database.unified_database import DatabaseManager

logger = logging.getLogger(__name__)


class TelegramBotCore:
    """Core Telegram bot functionality for client management"""
    
    def __init__(self, config: Config, db_manager: DatabaseManager):
        self.config = config
        self.db = db_manager
        self.clients: Dict[int, TelegramClient] = {}
        self.client_sessions: Dict[int, str] = {}
        self._rate_limiters: Dict[int, Dict[str, Any]] = {}
        
    async def initialize(self):
        """Initialize bot core"""
        try:
            logger.info("🔧 Initializing Telegram bot core...")
            
            # Ensure sessions directory exists
            sessions_dir = "sessions"
            if not os.path.exists(sessions_dir):
                os.makedirs(sessions_dir)
                logger.info(f"✅ Created sessions directory: {sessions_dir}")
            
            # Load existing sessions
            await self._load_existing_sessions()
            
            logger.info("✅ Telegram bot core initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize bot core: {e}")
            raise
    
    async def _load_existing_sessions(self):
        """Load existing Telegram sessions"""
        try:
            # First, check for orphaned session files and recover them
            await self._recover_orphaned_sessions()
            
            # Get all verified accounts from database
            accounts = await self.db.fetch_all(
                "SELECT * FROM telegram_accounts WHERE is_verified = TRUE AND is_active = TRUE"
            )
            
            loaded_count = 0
            for account in accounts:
                try:
                    success = await self._create_client_session(account)
                    if success:
                        loaded_count += 1
                except Exception as e:
                    logger.error(f"Failed to load session for account {account['id']}: {e}")
            
            logger.info(f"✅ Loaded {loaded_count} existing sessions")
            
        except Exception as e:
            logger.error(f"Error loading existing sessions: {e}")
    
    async def _recover_orphaned_sessions(self):
        """Recover session files that exist but aren't in the database"""
        try:
            import glob
            session_files = glob.glob("sessions/account_*.session")
            
            for session_file in session_files:
                try:
                    # Extract account ID from filename
                    account_id = int(session_file.split('account_')[1].split('.session')[0])
                    
                    # Check if account exists in database
                    existing = await self.db.fetch_one(
                        "SELECT id FROM telegram_accounts WHERE id = $1", account_id
                    )
                    
                    if not existing:
                        # Session file exists but no database record - recover it
                        await self._recover_session_from_file(account_id, session_file)
                        
                except Exception as e:
                    logger.error(f"Error checking session file {session_file}: {e}")
                    
        except Exception as e:
            logger.error(f"Error recovering orphaned sessions: {e}")
    
    async def _recover_session_from_file(self, account_id: int, session_file: str):
        """Recover account data from existing session file"""
        try:
            # Try to connect with the session file to get account info
            temp_client = TelegramClient(
                session_file.replace('.session', ''),
                self.config.DEFAULT_API_ID,
                self.config.DEFAULT_API_HASH
            )
            
            await temp_client.connect()
            
            if await temp_client.is_user_authorized():
                # Get user info from the session
                me = await temp_client.get_me()
                
                # Re-add the account to the database
                await self.db.execute_query(
                    """
                    INSERT INTO telegram_accounts 
                    (id, phone_number, api_id, api_hash, is_verified, is_active, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, TRUE, TRUE, NOW(), NOW())
                    ON CONFLICT (id) DO UPDATE SET
                    is_verified = TRUE, is_active = TRUE, updated_at = NOW()
                    """,
                    account_id, me.phone, self.config.DEFAULT_API_ID, self.config.DEFAULT_API_HASH
                )
                
                logger.info(f"🔄 RECOVERED: Session for account {me.phone} (ID: {account_id})")
                
            await temp_client.disconnect()
            
        except Exception as e:
            logger.error(f"Failed to recover session from {session_file}: {e}")
    
    async def _create_client_session(self, account: Dict[str, Any]) -> bool:
        """Create Telegram client session for account"""
        try:
            account_id = account['id']
            
            # Create client
            client = TelegramClient(
                f"sessions/account_{account_id}",
                account['api_id'],
                account['api_hash']
            )
            
            # Connect and verify session
            await client.connect()
            
            if await client.is_user_authorized():
                self.clients[account_id] = client
                self.client_sessions[account_id] = account['session_data']
                
                # Initialize rate limiter for this account
                self._rate_limiters[account_id] = {
                    'calls_this_minute': 0,
                    'calls_this_hour': 0,
                    'last_minute_reset': datetime.now(),
                    'last_hour_reset': datetime.now()
                }
                
                logger.info(f"✅ Session loaded for account {account['phone_number']}")
                return True
            else:
                await client.disconnect()
                logger.warning(f"⚠️ Session not authorized for account {account['phone_number']}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating client session: {e}")
            return False
    
    async def add_new_account(self, user_id: int, phone_number: str, 
                            api_id: int = None, api_hash: str = None) -> Dict[str, Any]:
        """Add new Telegram account"""
        try:
            # Use default API credentials if not provided
            if not api_id:
                api_id = self.config.DEFAULT_API_ID
            if not api_hash:
                api_hash = self.config.DEFAULT_API_HASH
            
            # Add account to database
            result = await self.db.add_telegram_account(user_id, phone_number, api_id, api_hash)
            if not result:
                return {'success': False, 'error': 'Failed to add account to database'}
            
            account_id = result
            
            # Create Telegram client
            client = TelegramClient(
                f"sessions/account_{account_id}",
                api_id,
                api_hash
            )
            
            # Connect and send verification code
            await client.connect()
            
            if not await client.is_user_authorized():
                # Request verification code
                sent_code = await client.send_code_request(phone_number)
                
                return {
                    'success': True,
                    'account_id': account_id,
                    'phone_code_hash': sent_code.phone_code_hash,
                    'message': 'Verification code sent. Please provide the code to complete setup.'
                }
            else:
                # Already authorized - save session
                session_data = client.session.save()
                await self.db.update_account_session(account_id, session_data)
                
                self.clients[account_id] = client
                self.client_sessions[account_id] = session_data
                
                return {
                    'success': True,
                    'account_id': account_id,
                    'message': 'Account added and authorized successfully'
                }
                
        except Exception as e:
            logger.error(f"Error adding new account: {e}")
            return {'success': False, 'error': str(e)}
    
    async def verify_account_code(self, account_id: int, code: str, 
                                phone_code_hash: str, password: str = None) -> Dict[str, Any]:
        """Verify account with code and optional 2FA password"""
        try:
            # Get account info
            account = await self.db.get_account_by_id(account_id)
            if not account:
                return {'success': False, 'error': 'Account not found'}
            
            # Get or create client
            client = self.clients.get(account_id)
            if not client:
                client = TelegramClient(
                    f"sessions/account_{account_id}",
                    account['api_id'],
                    account['api_hash']
                )
                await client.connect()
            
            try:
                # Sign in with code
                user = await client.sign_in(account['phone_number'], code, phone_code_hash=phone_code_hash)
                
            except SessionPasswordNeededError:
                # 2FA is enabled
                if not password:
                    return {
                        'success': False,
                        'requires_password': True,
                        'error': 'Two-factor authentication is enabled. Please provide your password.'
                    }
                
                # Sign in with password
                user = await client.sign_in(password=password)
            
            except PhoneCodeInvalidError:
                return {'success': False, 'error': 'Invalid verification code'}
            
            # Save session data
            session_data = client.session.save()
            await self.db.update_account_session(account_id, session_data)
            
            # Store client
            self.clients[account_id] = client
            self.client_sessions[account_id] = session_data
            
            # Initialize rate limiter
            self._rate_limiters[account_id] = {
                'calls_this_minute': 0,
                'calls_this_hour': 0,
                'last_minute_reset': datetime.now(),
                'last_hour_reset': datetime.now()
            }
            
            logger.info(f"✅ Account {account['phone_number']} verified successfully")
            
            return {
                'success': True,
                'user_info': {
                    'id': user.id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name
                },
                'message': 'Account verified and ready to use'
            }
            
        except Exception as e:
            logger.error(f"Error verifying account code: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_client(self, account_id: int) -> Optional[TelegramClient]:
        """Get Telegram client for account"""
        client = self.clients.get(account_id)
        if client and await client.is_user_authorized():
            return client
        return None
    
    async def check_rate_limit(self, account_id: int) -> bool:
        """Check if account has exceeded rate limits"""
        if account_id not in self._rate_limiters:
            return True
        
        limiter = self._rate_limiters[account_id]
        now = datetime.now()
        
        # Reset minute counter if needed
        if (now - limiter['last_minute_reset']).total_seconds() >= 60:
            limiter['calls_this_minute'] = 0
            limiter['last_minute_reset'] = now
        
        # Reset hour counter if needed
        if (now - limiter['last_hour_reset']).total_seconds() >= 3600:
            limiter['calls_this_hour'] = 0
            limiter['last_hour_reset'] = now
        
        # Check limits
        if limiter['calls_this_minute'] >= self.config.CALLS_PER_MINUTE_PER_ACCOUNT:
            return False
        
        if limiter['calls_this_hour'] >= self.config.CALLS_PER_HOUR_PER_ACCOUNT:
            return False
        
        return True
    
    async def increment_rate_limit(self, account_id: int):
        """Increment rate limit counters for account"""
        if account_id in self._rate_limiters:
            self._rate_limiters[account_id]['calls_this_minute'] += 1
            self._rate_limiters[account_id]['calls_this_hour'] += 1
    
    async def get_account_info(self, account_id: int) -> Optional[Dict[str, Any]]:
        """Get account information"""
        try:
            client = await self.get_client(account_id)
            if not client:
                return None
            
            # Get user info from Telegram
            me = await client.get_me()
            
            # Get database info
            db_account = await self.db.get_account_by_id(account_id)
            
            return {
                'account_id': account_id,
                'phone_number': db_account['phone_number'],
                'telegram_id': me.id,
                'username': me.username,
                'first_name': me.first_name,
                'last_name': me.last_name,
                'is_verified': db_account['is_verified'],
                'is_active': db_account['is_active'],
                'last_login': db_account['last_login'],
                'rate_limit_status': self._rate_limiters.get(account_id, {})
            }
            
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return None
    
    async def get_all_active_clients(self) -> List[Dict[str, Any]]:
        """Get all active client information"""
        active_clients = []
        
        for account_id, client in self.clients.items():
            try:
                if await client.is_user_authorized():
                    info = await self.get_account_info(account_id)
                    if info:
                        active_clients.append(info)
            except Exception as e:
                logger.error(f"Error checking client {account_id}: {e}")
        
        return active_clients
    
    async def disconnect_account(self, account_id: int) -> bool:
        """Disconnect and remove account session"""
        try:
            if account_id in self.clients:
                client = self.clients[account_id]
                await client.disconnect()
                del self.clients[account_id]
            
            if account_id in self.client_sessions:
                del self.client_sessions[account_id]
            
            if account_id in self._rate_limiters:
                del self._rate_limiters[account_id]
            
            # Deactivate in database
            await self.db.deactivate_account(account_id)
            
            logger.info(f"✅ Account {account_id} disconnected")
            return True
            
        except Exception as e:
            logger.error(f"Error disconnecting account {account_id}: {e}")
            return False
    
    async def shutdown(self):
        """Shutdown all clients"""
        try:
            logger.info("⏹️ Shutting down all Telegram clients...")
            
            # Disconnect all clients
            for account_id, client in self.clients.items():
                try:
                    await client.disconnect()
                except Exception as e:
                    logger.error(f"Error disconnecting client {account_id}: {e}")
            
            # Clear all data
            self.clients.clear()
            self.client_sessions.clear()
            self._rate_limiters.clear()
            
            logger.info("✅ All Telegram clients shut down")
            
        except Exception as e:
            logger.error(f"Error during bot core shutdown: {e}")
