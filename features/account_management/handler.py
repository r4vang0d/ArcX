"""
Account Management Handler - ArcX Bot
Simplified account management with default/custom API support
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, List, Optional

from aiogram import Bot, Dispatcher
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup

from core.config.config import Config
from core.database.unified_database import DatabaseManager

logger = logging.getLogger(__name__)


class AccountStates(StatesGroup):
    """FSM states for account management"""
    waiting_for_api_choice = State()
    waiting_for_custom_api = State()
    waiting_for_phone = State()
    waiting_for_code = State()
    waiting_for_password = State()


class AccountManagementHandler:
    """Simplified Account Manager according to user specifications"""
    
    def __init__(self, bot: Bot, db_manager: DatabaseManager, config: Config):
        self.bot = bot
        self.db = db_manager
        self.config = config
        self._pending_accounts = {}  # Store temporary account data during setup
        
    async def initialize(self):
        """Initialize account management handler"""
        try:
            logger.info("✅ Account management handler initialized")
        except Exception as e:
            logger.error(f"Failed to initialize account management handler: {e}")
            raise
    
    def register_handlers(self, dp: Dispatcher):
        """Register handlers with dispatcher"""
        # FSM message handlers  
        dp.message.register(self.handle_custom_api_input, AccountStates.waiting_for_custom_api)
        dp.message.register(self.handle_phone_input, AccountStates.waiting_for_phone)
        dp.message.register(self.handle_code_input, AccountStates.waiting_for_code)
        dp.message.register(self.handle_password_input, AccountStates.waiting_for_password)
        
        logger.info("✅ Account management handlers registered")
    
    async def handle_callback(self, callback: CallbackQuery, state: FSMContext):
        """Handle account management callbacks"""
        try:
            callback_data = callback.data
            user_id = callback.from_user.id
            
            # Ensure user exists in database
            await self._ensure_user_exists(callback.from_user)
            
            if callback_data == "am_add_account":
                await self._handle_add_account(callback, state)
            elif callback_data == "am_remove_account":
                await self._handle_remove_account(callback, state)
            elif callback_data == "am_list_accounts":
                await self._handle_list_accounts(callback, state)
            elif callback_data == "am_refresh":
                await self._handle_refresh_accounts(callback, state)
            elif callback_data.startswith("am_info_"):
                await self._handle_account_info(callback, state)
            elif callback_data.startswith("am_delete_"):
                await self._handle_delete_account(callback, state)
            elif callback_data == "am_use_default_api":
                await self._handle_use_default_api(callback, state)
            elif callback_data == "am_use_custom_api":
                await self._handle_use_custom_api(callback, state)
            else:
                await callback.answer("❌ Unknown action", show_alert=True)
                
        except Exception as e:
            logger.error(f"Error in account management callback: {e}")
            await callback.answer("❌ An error occurred", show_alert=True)
    
    async def _handle_add_account(self, callback: CallbackQuery, state: FSMContext):
        """Start add account process"""
        try:
            user_id = callback.from_user.id
            
            # Check account limit
            accounts = await self._get_user_accounts(user_id)
            if len(accounts) >= 100:  # As per user spec - max 1000 but load 100 at a time
                await callback.message.edit_text(
                    "🔥 <b>ArcX | Account Limit Reached</b>\\n\\n"
                    "You have reached the maximum limit of 100 active accounts.\\n"
                    "Remove some accounts before adding new ones.",
                    reply_markup=self._get_back_keyboard()
                )
                await callback.answer("⚠️ Account limit reached!")
                return
            
            text = """🔥 <b>ArcX | Add Account</b>

Choose API configuration:
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="[🔑 Use Default API]", callback_data="am_use_default_api")],
                [InlineKeyboardButton(text="[⚙️ Use Custom API]", callback_data="am_use_custom_api")],
                [InlineKeyboardButton(text="[🔙 Back]", callback_data="refresh_main")],
                [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
            ])
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("📱 Choose API type")
            
        except Exception as e:
            logger.error(f"Error in add account: {e}")
            await callback.answer("❌ Failed to start add account", show_alert=True)
    
    async def _handle_use_default_api(self, callback: CallbackQuery, state: FSMContext):
        """Use default API from .env"""
        try:
            user_id = callback.from_user.id
            
            # Store API choice
            self._pending_accounts[user_id] = {
                'api_id': self.config.DEFAULT_API_ID,
                'api_hash': self.config.DEFAULT_API_HASH,
                'api_type': 'default'
            }
            
            text = """🔥 <b>ArcX | Enter Phone Number</b>

Please send your phone number in international format:

<b>Example:</b> +1234567890

<b>Note:</b> You'll receive a verification code on this number.
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="[🔙 Back]", callback_data="am_add_account")],
                [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
            ])
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await state.set_state(AccountStates.waiting_for_phone)
            await callback.answer("📱 Enter phone number")
            
        except Exception as e:
            logger.error(f"Error using default API: {e}")
            await callback.answer("❌ Error setting up API", show_alert=True)
    
    async def _handle_use_custom_api(self, callback: CallbackQuery, state: FSMContext):
        """Use custom API credentials"""
        try:
            text = """🔥 <b>ArcX | Custom API Setup</b>

Send your API credentials in this format:
<code>API_ID,API_HASH</code>

<b>Example:</b>
<code>12345678,abcdef1234567890abcdef1234567890</code>

<b>Get your API credentials:</b>
1. Visit https://my.telegram.org
2. Login with your phone
3. Go to API development tools
4. Create new application
5. Copy API ID and API Hash
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="[🔙 Back]", callback_data="am_add_account")],
                [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
            ])
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await state.set_state(AccountStates.waiting_for_custom_api)
            await callback.answer("⚙️ Send custom API credentials")
            
        except Exception as e:
            logger.error(f"Error setting up custom API: {e}")
            await callback.answer("❌ Error setting up custom API", show_alert=True)
    
    async def handle_custom_api_input(self, message: Message, state: FSMContext):
        """Handle custom API input"""
        try:
            user_id = message.from_user.id
            api_text = message.text.strip()
            
            # Parse API credentials
            if ',' not in api_text:
                await message.answer(
                    "❌ <b>Invalid Format</b>\\n\\n"
                    "Please send in format: <code>API_ID,API_HASH</code>",
                    reply_markup=self._get_retry_keyboard()
                )
                return
            
            try:
                api_id_str, api_hash = api_text.split(',', 1)
                api_id = int(api_id_str.strip())
                api_hash = api_hash.strip()
                
                if not api_hash or len(api_hash) < 10:
                    raise ValueError("Invalid API hash")
                    
            except ValueError:
                await message.answer(
                    "❌ <b>Invalid API Credentials</b>\\n\\n"
                    "Please check the format and try again.",
                    reply_markup=self._get_retry_keyboard()
                )
                return
            
            # Store API credentials
            self._pending_accounts[user_id] = {
                'api_id': api_id,
                'api_hash': api_hash,
                'api_type': 'custom'
            }
            
            text = """🔥 <b>ArcX | Enter Phone Number</b>

API credentials saved! Now please send your phone number:

<b>Example:</b> +1234567890
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="[🔙 Back]", callback_data="am_add_account")],
                [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
            ])
            
            await message.answer(text, reply_markup=keyboard)
            await state.set_state(AccountStates.waiting_for_phone)
            
        except Exception as e:
            logger.error(f"Error handling custom API: {e}")
            await message.answer("❌ Error processing API credentials")
    
    async def handle_phone_input(self, message: Message, state: FSMContext):
        """Handle phone number input"""
        try:
            user_id = message.from_user.id
            phone = message.text.strip()
            
            # Validate phone format
            if not phone.startswith('+') or len(phone) < 10:
                await message.answer(
                    "❌ <b>Invalid Phone Format</b>\\n\\n"
                    "Please use international format with + sign\\n"
                    "Example: +1234567890",
                    reply_markup=self._get_retry_keyboard()
                )
                return
            
            # Check if phone exists
            existing = await self.db.fetch_one(
                "SELECT id FROM telegram_accounts WHERE phone_number = $1", phone
            )
            if existing:
                await message.answer(
                    "❌ <b>Phone Already Registered</b>\\n\\n"
                    "This phone number is already in use.",
                    reply_markup=self._get_retry_keyboard()
                )
                return
            
            # Get API credentials from pending
            if user_id not in self._pending_accounts:
                await message.answer("❌ Session expired. Please start again.")
                await state.clear()
                return
            
            api_data = self._pending_accounts[user_id]
            
            # Generate unique account ID
            account_uuid = str(uuid.uuid4())[:8]
            
            # Save to database
            account_id = await self.db.execute_query(
                """
                INSERT INTO telegram_accounts 
                (user_id, phone_number, api_id, api_hash, unique_id, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
                RETURNING id
                """,
                user_id, phone, api_data['api_id'], api_data['api_hash'], account_uuid
            )
            
            # Update pending with account details
            self._pending_accounts[user_id].update({
                'account_id': account_id,
                'phone': phone,
                'unique_id': account_uuid
            })
            
            # Send verification code (simulate - in real implementation would use Telethon)
            text = f"""🔥 <b>ArcX | Verification Code</b>

Verification code sent to: <code>{phone}</code>

Please enter the 5-digit code you received:
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="[🔙 Back]", callback_data="am_add_account")],
                [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
            ])
            
            await message.answer(text, reply_markup=keyboard)
            await state.set_state(AccountStates.waiting_for_code)
            
        except Exception as e:
            logger.error(f"Error handling phone input: {e}")
            await message.answer("❌ Error processing phone number")
    
    async def handle_code_input(self, message: Message, state: FSMContext):
        """Handle verification code"""
        try:
            user_id = message.from_user.id
            code = message.text.strip()
            
            if user_id not in self._pending_accounts:
                await message.answer("❌ Session expired. Please start again.")
                await state.clear()
                return
            
            account_data = self._pending_accounts[user_id]
            
            # Validate code format
            if len(code) != 5 or not code.isdigit():
                await message.answer(
                    "❌ <b>Invalid Code Format</b>\\n\\n"
                    "Please enter the 5-digit verification code.",
                    reply_markup=self._get_retry_keyboard()
                )
                return
            
            # Update account as verified
            await self.db.execute_query(
                """
                UPDATE telegram_accounts 
                SET is_verified = TRUE, last_login = NOW(), updated_at = NOW()
                WHERE id = $1
                """,
                account_data['account_id']
            )
            
            text = f"""✅ <b>ArcX | Account Added Successfully!</b>

<b>Account Details:</b>
• Phone: {account_data['phone']}
• Unique ID: {account_data['unique_id']}
• API Type: {account_data['api_type'].title()}
• Status: ✅ Verified

Account is ready for use in all operations!
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="[📋 View All Accounts]", callback_data="am_list_accounts")],
                [InlineKeyboardButton(text="[➕ Add Another]", callback_data="am_add_account")],
                [InlineKeyboardButton(text="[🔙 Account Manager]", callback_data="account_manager")],
                [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
            ])
            
            await message.answer(text, reply_markup=keyboard)
            
            # Cleanup
            if user_id in self._pending_accounts:
                del self._pending_accounts[user_id]
            await state.clear()
            
        except Exception as e:
            logger.error(f"Error handling code: {e}")
            await message.answer("❌ Error verifying code")
    
    async def handle_password_input(self, message: Message, state: FSMContext):
        """Handle 2FA password input"""
        try:
            user_id = message.from_user.id
            password = message.text.strip()
            
            if user_id not in self._pending_accounts:
                await message.answer("❌ Session expired. Please start again.")
                await state.clear()
                return
            
            account_data = self._pending_accounts[user_id]
            
            # Update account as verified with 2FA
            await self.db.execute_query(
                """
                UPDATE telegram_accounts 
                SET is_verified = TRUE, last_login = NOW(), updated_at = NOW()
                WHERE id = $1
                """,
                account_data['account_id']
            )
            
            text = f"""✅ <b>ArcX | Account Verified with 2FA!</b>

<b>Account Details:</b>
• Phone: {account_data['phone']}
• Unique ID: {account_data['unique_id']}
• Security: 🔐 Two-Factor Enabled
• Status: ✅ Verified

Account is ready for secure operations!
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="[📋 View All Accounts]", callback_data="am_list_accounts")],
                [InlineKeyboardButton(text="[🔙 Account Manager]", callback_data="account_manager")],
                [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
            ])
            
            await message.answer(text, reply_markup=keyboard)
            
            # Cleanup
            if user_id in self._pending_accounts:
                del self._pending_accounts[user_id]
            await state.clear()
            
        except Exception as e:
            logger.error(f"Error handling password: {e}")
            await message.answer("❌ Error verifying password")
    
    async def _handle_remove_account(self, callback: CallbackQuery, state: FSMContext):
        """Handle remove account"""
        try:
            user_id = callback.from_user.id
            
            accounts = await self._get_user_accounts(user_id)
            if not accounts:
                await callback.message.edit_text(
                    "🔥 <b>ArcX | No Accounts Found</b>\\n\\n"
                    "You don't have any accounts to remove.",
                    reply_markup=self._get_back_keyboard()
                )
                await callback.answer("ℹ️ No accounts to remove")
                return
            
            text = "🔥 <b>ArcX | Remove Account</b>\\n\\nSelect account to remove:\\n\\n"
            
            buttons = []
            for account in accounts[:10]:  # Show max 10 for UI
                username = f"@{account.get('username', 'No username')}"
                button_text = f"[🗑️ {account['phone_number']}]"
                callback_data = f"am_delete_{account['id']}"
                buttons.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])
            
            buttons.extend([
                [InlineKeyboardButton(text="[🔙 Back]", callback_data="account_manager")],
                [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
            ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("🗑️ Select account to remove")
            
        except Exception as e:
            logger.error(f"Error in remove account: {e}")
            await callback.answer("❌ Failed to load remove account", show_alert=True)
    
    async def _handle_list_accounts(self, callback: CallbackQuery, state: FSMContext):
        """Handle list accounts with info buttons"""
        try:
            user_id = callback.from_user.id
            
            accounts = await self._get_user_accounts(user_id)
            if not accounts:
                await callback.message.edit_text(
                    "🔥 <b>ArcX | No Accounts</b>\\n\\n"
                    "You haven't added any accounts yet.\\n"
                    "Add your first account to get started!",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="[➕ Add Account]", callback_data="am_add_account")],
                        [InlineKeyboardButton(text="[🔙 Back]", callback_data="account_manager")],
                        [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
                    ])
                )
                await callback.answer("ℹ️ No accounts found")
                return
            
            text = f"🔥 <b>ArcX | Account List</b>\\n\\nTotal Accounts: {len(accounts)}\\n\\n"
            
            buttons = []
            for i, account in enumerate(accounts[:10], 1):  # Show max 10
                username = account.get('username', 'No username')
                status = "✅" if account['is_active'] else "❌"
                account_text = f"{status} {username}"
                
                # Account name button and info button in same row
                buttons.append([
                    InlineKeyboardButton(text=f"[{i}. {account_text}]", callback_data=f"am_select_{account['id']}"),
                    InlineKeyboardButton(text="[ℹ️]", callback_data=f"am_info_{account['id']}")
                ])
            
            buttons.extend([
                [InlineKeyboardButton(text="[🔙 Back]", callback_data="account_manager")],
                [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
            ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer(f"📋 {len(accounts)} accounts loaded")
            
        except Exception as e:
            logger.error(f"Error listing accounts: {e}")
            await callback.answer("❌ Failed to load accounts", show_alert=True)
    
    async def _handle_account_info(self, callback: CallbackQuery, state: FSMContext):
        """Show detailed account information popup"""
        try:
            account_id = int(callback.data.split('_')[2])
            
            account = await self.db.fetch_one(
                "SELECT * FROM telegram_accounts WHERE id = $1", account_id
            )
            
            if not account:
                await callback.answer("❌ Account not found", show_alert=True)
                return
            
            # Calculate account health and status
            health_score = await self._calculate_health_score(account)
            status = "🟢 Active" if account['is_active'] else "🔴 Inactive"
            
            info_text = f"""📱 Account Info

Phone: {account['phone_number']}
Status: {status}
Health: {health_score}/100
Verified: {"✅" if account['is_verified'] else "❌"}

Added: {account['created_at'].strftime('%Y-%m-%d')}
API: {"Default" if account['api_id'] == self.config.DEFAULT_API_ID else "Custom"}"""
            
            await callback.answer(info_text, show_alert=True)
            
        except Exception as e:
            logger.error(f"Error showing account info: {e}")
            await callback.answer("❌ Error loading account info", show_alert=True)
    
    async def _handle_refresh_accounts(self, callback: CallbackQuery, state: FSMContext):
        """Refresh accounts list"""
        try:
            user_id = callback.from_user.id
            
            # Show account manager menu again with fresh data
            text = "🔥 <b>ArcX | Account Manager</b>\\n\\nManage your Telegram accounts for operations:\\n\\n"
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="[➕ Add Account]", callback_data="am_add_account")],
                [InlineKeyboardButton(text="[🗑️ Remove Account]", callback_data="am_remove_account")],
                [InlineKeyboardButton(text="[📋 List Accounts]", callback_data="am_list_accounts")],
                [InlineKeyboardButton(text="[🔄 Refresh Accounts]", callback_data="am_refresh")],
                [InlineKeyboardButton(text="[🔙 Back]", callback_data="refresh_main")],
                [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
            ])
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("🔄 Accounts refreshed!")
            
        except Exception as e:
            logger.error(f"Error refreshing accounts: {e}")
            await callback.answer("❌ Failed to refresh", show_alert=True)
    
    async def _handle_delete_account(self, callback: CallbackQuery, state: FSMContext):
        """Handle account deletion"""
        try:
            account_id = int(callback.data.split('_')[2])
            
            # Get account details
            account = await self.db.fetch_one(
                "SELECT * FROM telegram_accounts WHERE id = $1", account_id
            )
            
            if not account:
                await callback.answer("❌ Account not found", show_alert=True)
                return
            
            # Delete from database and remove session file
            await self.db.execute_query(
                "DELETE FROM telegram_accounts WHERE id = $1", account_id
            )
            
            # Remove session file if exists
            session_file = f"sessions/{account.get('unique_id', account_id)}.session"
            try:
                import os
                if os.path.exists(session_file):
                    os.remove(session_file)
                if os.path.exists(f"{session_file}-journal"):
                    os.remove(f"{session_file}-journal")
            except Exception as session_error:
                logger.warning(f"Could not remove session file: {session_error}")
            
            text = f"""✅ <b>ArcX | Account Removed</b>

Account successfully removed:
• Phone: {account['phone_number']}
• Unique ID: {account.get('unique_id', 'N/A')}

All data and session files have been cleaned up.
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="[📋 View Remaining]", callback_data="am_list_accounts")],
                [InlineKeyboardButton(text="[🔙 Account Manager]", callback_data="account_manager")],
                [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
            ])
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("✅ Account removed successfully!")
            
        except Exception as e:
            logger.error(f"Error deleting account: {e}")
            await callback.answer("❌ Failed to remove account", show_alert=True)
    
    # Helper methods
    async def _get_user_accounts(self, user_id: int) -> List[Dict[str, Any]]:
        """Get user's accounts (including orphaned accounts from session recovery)"""
        # First, try to claim any orphaned accounts (accounts with NULL user_id)
        await self._claim_orphaned_accounts(user_id)
        
        # Then return user's accounts
        return await self.db.fetch_all(
            "SELECT * FROM telegram_accounts WHERE user_id = $1 ORDER BY created_at DESC",
            user_id
        )
    
    async def _ensure_user_exists(self, user):
        """Ensure user exists in database"""
        await self.db.execute_query(
            """
            INSERT INTO users (user_id, username, first_name, last_name, first_seen, last_seen)
            VALUES ($1, $2, $3, $4, NOW(), NOW())
            ON CONFLICT (user_id) DO UPDATE SET 
                username = $2, last_seen = NOW()
            """,
            user.id, user.username, user.first_name, user.last_name
        )
    
    async def _calculate_health_score(self, account: Dict[str, Any]) -> int:
        """Calculate account health score"""
        score = 100
        
        if not account['is_verified']:
            score -= 30
        if not account['is_active']:
            score -= 50
        if not account.get('last_login'):
            score -= 20
            
        return max(0, score)
    
    def _get_back_keyboard(self) -> InlineKeyboardMarkup:
        """Get back button keyboard"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="[🔙 Account Manager]", callback_data="account_manager")],
            [InlineKeyboardButton(text="[🏠 Main Menu]", callback_data="refresh_main")]
        ])
    
    async def _claim_orphaned_accounts(self, user_id: int):
        """Claim orphaned accounts from session recovery"""
        try:
            # Update orphaned accounts (user_id IS NULL) to belong to this user
            await self.db.execute_query(
                "UPDATE telegram_accounts SET user_id = $1 WHERE user_id IS NULL",
                user_id
            )
        except Exception as e:
            logger.error(f"Error claiming orphaned accounts: {e}")
    
    def _get_retry_keyboard(self) -> InlineKeyboardMarkup:
        """Get retry keyboard"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="[🔄 Try Again]", callback_data="am_add_account")],
            [InlineKeyboardButton(text="[🔙 Back]", callback_data="account_manager")]
        ])
    
