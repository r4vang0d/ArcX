"""
Account Management Handler
Handles Telegram account management, authentication, and monitoring
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup

from core.config.config import Config
from core.database.unified_database import DatabaseManager
from core.database.universal_access import UniversalDatabaseAccess
from core.bot.telegram_bot import TelegramBotCore

logger = logging.getLogger(__name__)


class AccountStates(StatesGroup):
    """FSM states for account management"""
    waiting_for_phone = State()
    waiting_for_code = State()
    waiting_for_password = State()
    waiting_for_api_credentials = State()


class AccountManagementHandler:
    """Handler for Telegram account management"""
    
    def __init__(self, bot: Bot, db_manager: DatabaseManager, config: Config):
        self.bot = bot
        self.db = db_manager
        self.config = config
        self.universal_db = UniversalDatabaseAccess(db_manager)
        self.bot_core = TelegramBotCore(config, db_manager)
        self._pending_verifications = {}
        
    async def initialize(self):
        """Initialize account management handler"""
        try:
            await self.bot_core.initialize()
            logger.info("✅ Account management handler initialized")
        except Exception as e:
            logger.error(f"Failed to initialize account management handler: {e}")
            raise
    
    def register_handlers(self, dp: Dispatcher):
        """Register handlers with dispatcher"""
        dp.callback_query.register(
            self.handle_callback,
            lambda c: c.data.startswith('am_')
        )
        
        # FSM handlers
        dp.message.register(
            self.handle_phone_input,
            AccountStates.waiting_for_phone
        )
        
        dp.message.register(
            self.handle_code_input,
            AccountStates.waiting_for_code
        )
        
        dp.message.register(
            self.handle_password_input,
            AccountStates.waiting_for_password
        )
        
        logger.info("✅ Account management handlers registered")
    
    async def handle_callback(self, callback: CallbackQuery, state: FSMContext):
        """Handle account management callbacks"""
        try:
            callback_data = callback.data
            user_id = callback.from_user.id
            
            # Ensure user exists
            await self.universal_db.ensure_user_exists(
                user_id,
                callback.from_user.username,
                callback.from_user.first_name,
                callback.from_user.last_name
            )
            
            if callback_data == "am_add_account":
                await self._handle_add_account(callback, state)
            elif callback_data == "am_list_accounts":
                await self._handle_list_accounts(callback, state)
            elif callback_data == "am_settings":
                await self._handle_account_settings(callback, state)
            elif callback_data == "am_health":
                await self._handle_health_check(callback, state)
            elif callback_data.startswith("am_account_"):
                await self._handle_account_details(callback, state)
            elif callback_data.startswith("am_delete_"):
                await self._handle_delete_account(callback, state)
            elif callback_data.startswith("am_activate_"):
                await self._handle_activate_account(callback, state)
            elif callback_data.startswith("am_deactivate_"):
                await self._handle_deactivate_account(callback, state)
            else:
                await callback.answer("❌ Unknown account management action", show_alert=True)
                
        except Exception as e:
            logger.error(f"Error in account management callback: {e}")
            await callback.answer("❌ An error occurred", show_alert=True)
    
    async def _handle_add_account(self, callback: CallbackQuery, state: FSMContext):
        """Handle add account process"""
        try:
            user_id = callback.from_user.id
            
            # Check account limit
            existing_accounts = await self.db.get_user_accounts(user_id)
            if len(existing_accounts) >= self.config.MAX_ACTIVE_CLIENTS:
                await callback.message.edit_text(
                    f"⚠️ <b>Account Limit Reached</b>\n\n"
                    f"You have reached the maximum limit of {self.config.MAX_ACTIVE_CLIENTS} accounts.\n"
                    f"Please remove some accounts before adding new ones.",
                    reply_markup=self._get_account_limit_keyboard()
                )
                return
            
            text = """
📱 <b>Add New Telegram Account</b>

To add a new Telegram account, you'll need:

<b>📝 Required Information:</b>
• Phone number (with country code)
• Access to receive SMS/calls
• Two-factor password (if enabled)

<b>🔐 API Credentials (Optional):</b>
• API ID and API Hash from https://my.telegram.org
• If not provided, default credentials will be used

<b>⚠️ Important Notes:</b>
• Account will be used for view boosting operations
• Keep your phone accessible for verification
• Account should not be used elsewhere simultaneously

Please send your phone number in international format (e.g., +1234567890):
            """
            
            keyboard = self._get_add_account_keyboard()
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await state.set_state(AccountStates.waiting_for_phone)
            await callback.answer("📱 Please provide phone number")
            
        except Exception as e:
            logger.error(f"Error in add account: {e}")
            await callback.answer("❌ Failed to start add account process", show_alert=True)
    
    async def _handle_list_accounts(self, callback: CallbackQuery, state: FSMContext):
        """Handle list accounts"""
        try:
            user_id = callback.from_user.id
            
            # Get accounts with health information
            accounts = await self.universal_db.get_accounts_with_health(user_id)
            
            if not accounts:
                await callback.message.edit_text(
                    "📱 <b>No Accounts Found</b>\n\n"
                    "You haven't added any Telegram accounts yet.\n"
                    "Add your first account to start using the bot features!",
                    reply_markup=self._get_no_accounts_keyboard()
                )
                return
            
            text = f"📱 <b>Your Telegram Accounts ({len(accounts)})</b>\n\n"
            
            for i, account in enumerate(accounts, 1):
                status_emoji = "🟢" if account['is_active'] else "🔴"
                health_emoji = self._get_health_emoji(account['health_score'])
                
                text += (
                    f"{status_emoji} <b>{i}. {account['phone_number']}</b>\n"
                    f"   {health_emoji} Health: {account['health_score']}/100\n"
                    f"   📅 Added: {account['created_at'].strftime('%Y-%m-%d')}\n"
                )
                
                if account['health_issues']:
                    text += f"   ⚠️ Issues: {', '.join(account['health_issues'][:2])}\n"
                
                text += "\n"
            
            # Summary stats
            active_count = len([a for a in accounts if a['is_active']])
            verified_count = len([a for a in accounts if a['is_verified']])
            avg_health = sum(a['health_score'] for a in accounts) / len(accounts)
            
            text += f"""
<b>📊 Summary:</b>
• Active: {active_count}/{len(accounts)} accounts
• Verified: {verified_count}/{len(accounts)} accounts  
• Average Health: {avg_health:.0f}/100
• Total Capacity: {len(accounts)}/{self.config.MAX_ACTIVE_CLIENTS}
            """
            
            keyboard = self._get_accounts_list_keyboard(accounts[:5])
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer(f"📱 {len(accounts)} accounts loaded")
            
        except Exception as e:
            logger.error(f"Error listing accounts: {e}")
            await callback.answer("❌ Failed to load accounts", show_alert=True)
    
    async def _handle_account_settings(self, callback: CallbackQuery, state: FSMContext):
        """Handle account settings"""
        try:
            user_id = callback.from_user.id
            
            # Get user's account settings
            user = await self.db.get_user(user_id)
            settings = user.get('settings', {}) if user else {}
            account_settings = settings.get('accounts', {})
            
            text = f"""
⚙️ <b>Account Management Settings</b>

<b>🔧 Global Account Settings:</b>
• Auto Health Monitoring: {'✅ Enabled' if account_settings.get('auto_health_check', True) else '❌ Disabled'}
• Rate Limit Protection: {'✅ Enabled' if account_settings.get('rate_limit_protection', True) else '❌ Disabled'}
• Auto Account Rotation: {'✅ Enabled' if account_settings.get('auto_rotation', True) else '❌ Disabled'}
• Session Backup: {'✅ Enabled' if account_settings.get('session_backup', False) else '❌ Disabled'}

<b>⚡ Performance Settings:</b>
• Max Concurrent Operations: {account_settings.get('max_concurrent', 5)}
• Health Check Interval: {account_settings.get('health_interval', 300)} seconds
• Auto Retry Failed Operations: {'✅ Yes' if account_settings.get('auto_retry', True) else '❌ No'}
• Intelligent Load Balancing: {'✅ Yes' if account_settings.get('load_balancing', True) else '❌ No'}

<b>🚨 Alert Settings:</b>
• Health Alerts: {'✅ Enabled' if account_settings.get('health_alerts', True) else '❌ Disabled'}
• Rate Limit Alerts: {'✅ Enabled' if account_settings.get('rate_alerts', True) else '❌ Disabled'}
• Account Status Changes: {'✅ Enabled' if account_settings.get('status_alerts', True) else '❌ Disabled'}

<b>🔐 Security Settings:</b>
• Two-Factor Backup: {'✅ Enabled' if account_settings.get('2fa_backup', False) else '❌ Disabled'}
• Session Encryption: {'✅ Enabled' if account_settings.get('encryption', True) else '❌ Disabled'}
• Auto Logout Inactive: {'✅ Enabled' if account_settings.get('auto_logout', False) else '❌ Disabled'}
            """
            
            keyboard = self._get_settings_keyboard()
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("⚙️ Account settings loaded")
            
        except Exception as e:
            logger.error(f"Error in account settings: {e}")
            await callback.answer("❌ Failed to load settings", show_alert=True)
    
    async def _handle_health_check(self, callback: CallbackQuery, state: FSMContext):
        """Handle health check"""
        try:
            user_id = callback.from_user.id
            
            # Get accounts with health information
            accounts = await self.universal_db.get_accounts_with_health(user_id)
            
            if not accounts:
                await callback.message.edit_text(
                    "📱 <b>No Accounts to Check</b>\n\n"
                    "Add accounts first to perform health checks.",
                    reply_markup=self._get_no_accounts_keyboard()
                )
                return
            
            # Show initial checking message
            await callback.message.edit_text(
                f"🔍 <b>Performing Health Check...</b>\n\n"
                f"Checking {len(accounts)} accounts...\n"
                f"This may take a few moments.",
                reply_markup=None
            )
            
            # Perform health checks
            health_results = await self._perform_health_checks(user_id, accounts)
            
            # Generate health report
            text = f"""
💚 <b>Account Health Report</b>

<b>📊 Overall Health Score: {health_results['overall_score']:.0f}/100</b>

<b>✅ Healthy Accounts ({health_results['healthy_count']}):</b>
"""
            
            for account in health_results['healthy_accounts']:
                text += f"• {account['phone_number']} - {account['health_score']}/100\n"
            
            if health_results['warning_accounts']:
                text += f"\n<b>⚠️ Accounts Needing Attention ({len(health_results['warning_accounts'])}):</b>\n"
                for account in health_results['warning_accounts']:
                    text += f"• {account['phone_number']} - {account['health_score']}/100\n"
                    text += f"  Issues: {', '.join(account['health_issues'][:2])}\n"
            
            if health_results['critical_accounts']:
                text += f"\n<b>🚨 Critical Accounts ({len(health_results['critical_accounts'])}):</b>\n"
                for account in health_results['critical_accounts']:
                    text += f"• {account['phone_number']} - {account['health_score']}/100\n"
                    text += f"  Issues: {', '.join(account['health_issues'][:2])}\n"
            
            text += f"""
<b>📈 Health Trends:</b>
• Accounts Improved: {health_results['improved_count']}
• Accounts Declined: {health_results['declined_count']}
• Stable Accounts: {health_results['stable_count']}

<b>💡 Recommendations:</b>
"""
            
            for recommendation in health_results['recommendations']:
                text += f"• {recommendation}\n"
            
            keyboard = self._get_health_check_keyboard()
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer("💚 Health check completed")
            
        except Exception as e:
            logger.error(f"Error in health check: {e}")
            await callback.answer("❌ Health check failed", show_alert=True)
    
    async def handle_phone_input(self, message: Message, state: FSMContext):
        """Handle phone number input"""
        try:
            phone_number = message.text.strip()
            user_id = message.from_user.id
            
            # Validate phone number format
            if not self._validate_phone_number(phone_number):
                await message.answer(
                    "❌ <b>Invalid Phone Number</b>\n\n"
                    "Please provide a valid phone number in international format.\n"
                    "Example: +1234567890\n\n"
                    "Make sure to include the country code.",
                    reply_markup=self._get_retry_phone_keyboard()
                )
                return
            
            # Check if phone number already exists
            existing = await self.db.fetch_one(
                "SELECT id FROM telegram_accounts WHERE phone_number = $1",
                phone_number
            )
            
            if existing:
                await message.answer(
                    "⚠️ <b>Phone Number Already Registered</b>\n\n"
                    "This phone number is already associated with an account.\n"
                    "Each phone number can only be used once.",
                    reply_markup=self._get_retry_phone_keyboard()
                )
                return
            
            # Show processing message
            processing_msg = await message.answer("📱 <b>Adding Account...</b>\n\nSending verification code...")
            
            # Add account using bot core
            result = await self.bot_core.add_new_account(
                user_id, phone_number, 
                self.config.DEFAULT_API_ID, 
                self.config.DEFAULT_API_HASH
            )
            
            if result['success']:
                # Store verification data
                self._pending_verifications[user_id] = {
                    'account_id': result['account_id'],
                    'phone_code_hash': result.get('phone_code_hash'),
                    'phone_number': phone_number
                }
                
                await processing_msg.edit_text(
                    f"📨 <b>Verification Code Sent!</b>\n\n"
                    f"A verification code has been sent to:\n"
                    f"<code>{phone_number}</code>\n\n"
                    f"Please enter the verification code you received:",
                    reply_markup=self._get_code_input_keyboard()
                )
                
                await state.set_state(AccountStates.waiting_for_code)
            else:
                await processing_msg.edit_text(
                    f"❌ <b>Failed to Add Account</b>\n\n"
                    f"Error: {result['error']}\n\n"
                    f"Please try again or contact support if the issue persists.",
                    reply_markup=self._get_retry_phone_keyboard()
                )
                await state.clear()
            
        except Exception as e:
            logger.error(f"Error handling phone input: {e}")
            await message.answer(
                "❌ An error occurred while processing your phone number. Please try again.",
                reply_markup=self._get_retry_phone_keyboard()
            )
            await state.clear()
    
    async def handle_code_input(self, message: Message, state: FSMContext):
        """Handle verification code input"""
        try:
            code = message.text.strip()
            user_id = message.from_user.id
            
            if user_id not in self._pending_verifications:
                await message.answer(
                    "❌ <b>Verification Session Expired</b>\n\n"
                    "Please start the account addition process again.",
                    reply_markup=self._get_restart_keyboard()
                )
                await state.clear()
                return
            
            verification_data = self._pending_verifications[user_id]
            
            # Show processing message
            processing_msg = await message.answer("🔐 <b>Verifying Code...</b>\n\nPlease wait...")
            
            # Verify code
            result = await self.bot_core.verify_account_code(
                verification_data['account_id'],
                code,
                verification_data['phone_code_hash']
            )
            
            if result['success']:
                # Account verified successfully
                await processing_msg.edit_text(
                    f"✅ <b>Account Added Successfully!</b>\n\n"
                    f"📱 <b>Account Details:</b>\n"
                    f"• Phone: {verification_data['phone_number']}\n"
                    f"• User ID: {result['user_info']['id']}\n"
                    f"• Username: @{result['user_info']['username'] or 'None'}\n"
                    f"• Name: {result['user_info']['first_name']} {result['user_info']['last_name'] or ''}\n\n"
                    f"🚀 Your account is now ready for use in all bot operations!",
                    reply_markup=self._get_account_added_keyboard()
                )
                
                # Cleanup
                del self._pending_verifications[user_id]
                await state.clear()
                
            elif result.get('requires_password'):
                # 2FA enabled, need password
                await processing_msg.edit_text(
                    f"🔐 <b>Two-Factor Authentication</b>\n\n"
                    f"Your account has two-factor authentication enabled.\n"
                    f"Please enter your cloud password:",
                    reply_markup=self._get_password_input_keyboard()
                )
                
                await state.set_state(AccountStates.waiting_for_password)
                
            else:
                # Verification failed
                await processing_msg.edit_text(
                    f"❌ <b>Verification Failed</b>\n\n"
                    f"Error: {result['error']}\n\n"
                    f"Please check the code and try again.",
                    reply_markup=self._get_retry_code_keyboard()
                )
            
        except Exception as e:
            logger.error(f"Error handling code input: {e}")
            await message.answer(
                "❌ An error occurred during verification. Please try again.",
                reply_markup=self._get_retry_code_keyboard()
            )
    
    async def handle_password_input(self, message: Message, state: FSMContext):
        """Handle 2FA password input"""
        try:
            password = message.text.strip()
            user_id = message.from_user.id
            
            if user_id not in self._pending_verifications:
                await message.answer(
                    "❌ <b>Verification Session Expired</b>\n\n"
                    "Please start the account addition process again.",
                    reply_markup=self._get_restart_keyboard()
                )
                await state.clear()
                return
            
            verification_data = self._pending_verifications[user_id]
            
            # Show processing message
            processing_msg = await message.answer("🔐 <b>Verifying Password...</b>\n\nPlease wait...")
            
            # Verify with password
            result = await self.bot_core.verify_account_code(
                verification_data['account_id'],
                None,  # No code needed for password verification
                verification_data['phone_code_hash'],
                password
            )
            
            if result['success']:
                # Account verified successfully
                await processing_msg.edit_text(
                    f"✅ <b>Account Added Successfully!</b>\n\n"
                    f"📱 <b>Account Details:</b>\n"
                    f"• Phone: {verification_data['phone_number']}\n"
                    f"• User ID: {result['user_info']['id']}\n"
                    f"• Username: @{result['user_info']['username'] or 'None'}\n"
                    f"• Name: {result['user_info']['first_name']} {result['user_info']['last_name'] or ''}\n\n"
                    f"🔐 Two-factor authentication verified successfully!\n"
                    f"🚀 Your account is now ready for use!",
                    reply_markup=self._get_account_added_keyboard()
                )
                
                # Cleanup
                del self._pending_verifications[user_id]
                await state.clear()
                
            else:
                # Password verification failed
                await processing_msg.edit_text(
                    f"❌ <b>Password Verification Failed</b>\n\n"
                    f"Error: {result['error']}\n\n"
                    f"Please check your cloud password and try again.",
                    reply_markup=self._get_retry_password_keyboard()
                )
            
        except Exception as e:
            logger.error(f"Error handling password input: {e}")
            await message.answer(
                "❌ An error occurred during password verification. Please try again.",
                reply_markup=self._get_retry_password_keyboard()
            )
    
    async def _perform_health_checks(self, user_id: int, accounts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Perform comprehensive health checks on accounts"""
        try:
            healthy_accounts = []
            warning_accounts = []
            critical_accounts = []
            
            for account in accounts:
                # Account is already processed with health score
                if account['health_score'] >= 80:
                    healthy_accounts.append(account)
                elif account['health_score'] >= 50:
                    warning_accounts.append(account)
                else:
                    critical_accounts.append(account)
            
            overall_score = sum(a['health_score'] for a in accounts) / len(accounts) if accounts else 0
            
            # Generate recommendations
            recommendations = []
            if warning_accounts:
                recommendations.append("Review accounts with warnings and address identified issues")
            if critical_accounts:
                recommendations.append("Urgent attention needed for critical accounts")
            if len(healthy_accounts) < len(accounts) * 0.8:
                recommendations.append("Consider adding more accounts for better distribution")
            
            if not recommendations:
                recommendations.append("All accounts are in good health!")
            
            return {
                'overall_score': overall_score,
                'healthy_count': len(healthy_accounts),
                'healthy_accounts': healthy_accounts,
                'warning_accounts': warning_accounts,
                'critical_accounts': critical_accounts,
                'improved_count': 0,  # Would track from historical data
                'declined_count': 0,  # Would track from historical data
                'stable_count': len(accounts),  # Would track from historical data
                'recommendations': recommendations
            }
            
        except Exception as e:
            logger.error(f"Error performing health checks: {e}")
            return {
                'overall_score': 0, 'healthy_count': 0, 'healthy_accounts': [],
                'warning_accounts': [], 'critical_accounts': [],
                'improved_count': 0, 'declined_count': 0, 'stable_count': 0,
                'recommendations': ['Health check failed - please try again']
            }
    
    def _validate_phone_number(self, phone: str) -> bool:
        """Validate phone number format"""
        import re
        # Basic validation for international format
        pattern = r'^\+[1-9]\d{1,14}$'
        return bool(re.match(pattern, phone))
    
    def _get_health_emoji(self, score: int) -> str:
        """Get health emoji based on score"""
        if score >= 80:
            return "💚"
        elif score >= 50:
            return "💛"
        else:
            return "❤️"
    
    # Keyboard methods
    def _get_add_account_keyboard(self) -> InlineKeyboardMarkup:
        """Get add account keyboard"""
        buttons = [
            [InlineKeyboardButton(text="❓ Phone Format Help", callback_data="am_phone_help")],
            [InlineKeyboardButton(text="🔙 Back to Account Management", callback_data="account_management")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_no_accounts_keyboard(self) -> InlineKeyboardMarkup:
        """Get no accounts keyboard"""
        buttons = [
            [InlineKeyboardButton(text="➕ Add First Account", callback_data="am_add_account")],
            [InlineKeyboardButton(text="❓ How to Add Accounts", callback_data="am_help")],
            [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="refresh_main")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_accounts_list_keyboard(self, accounts: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
        """Get accounts list keyboard"""
        buttons = []
        
        # Add account buttons (max 5)
        for account in accounts[:5]:
            status_emoji = "🟢" if account['is_active'] else "🔴"
            buttons.append([
                InlineKeyboardButton(
                    text=f"{status_emoji} {account['phone_number']}",
                    callback_data=f"am_account_{account['id']}"
                )
            ])
        
        # Control buttons
        buttons.extend([
            [
                InlineKeyboardButton(text="➕ Add Account", callback_data="am_add_account"),
                InlineKeyboardButton(text="💚 Health Check", callback_data="am_health")
            ],
            [
                InlineKeyboardButton(text="⚙️ Settings", callback_data="am_settings"),
                InlineKeyboardButton(text="🔄 Refresh", callback_data="am_list_accounts")
            ],
            [
                InlineKeyboardButton(text="🔙 Back to Menu", callback_data="refresh_main")
            ]
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_settings_keyboard(self) -> InlineKeyboardMarkup:
        """Get settings keyboard"""
        buttons = [
            [
                InlineKeyboardButton(text="💚 Health Settings", callback_data="am_health_settings"),
                InlineKeyboardButton(text="⚡ Performance", callback_data="am_performance_settings")
            ],
            [
                InlineKeyboardButton(text="🚨 Alert Settings", callback_data="am_alert_settings"),
                InlineKeyboardButton(text="🔐 Security", callback_data="am_security_settings")
            ],
            [
                InlineKeyboardButton(text="💾 Save Changes", callback_data="am_save_settings"),
                InlineKeyboardButton(text="🔄 Reset to Default", callback_data="am_reset_settings")
            ],
            [
                InlineKeyboardButton(text="🔙 Back to Account Management", callback_data="account_management")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_health_check_keyboard(self) -> InlineKeyboardMarkup:
        """Get health check keyboard"""
        buttons = [
            [
                InlineKeyboardButton(text="🔍 Detailed Report", callback_data="am_detailed_health"),
                InlineKeyboardButton(text="🔧 Fix Issues", callback_data="am_fix_issues")
            ],
            [
                InlineKeyboardButton(text="📊 Health History", callback_data="am_health_history"),
                InlineKeyboardButton(text="⚙️ Auto Monitoring", callback_data="am_auto_monitoring")
            ],
            [
                InlineKeyboardButton(text="🔄 Check Again", callback_data="am_health"),
                InlineKeyboardButton(text="📱 View Accounts", callback_data="am_list_accounts")
            ],
            [
                InlineKeyboardButton(text="🔙 Back to Account Management", callback_data="account_management")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_account_limit_keyboard(self) -> InlineKeyboardMarkup:
        """Get account limit keyboard"""
        buttons = [
            [InlineKeyboardButton(text="📱 Manage Accounts", callback_data="am_list_accounts")],
            [InlineKeyboardButton(text="🔙 Back to Account Management", callback_data="account_management")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_retry_phone_keyboard(self) -> InlineKeyboardMarkup:
        """Get retry phone keyboard"""
        buttons = [
            [InlineKeyboardButton(text="🔄 Try Again", callback_data="am_add_account")],
            [InlineKeyboardButton(text="❓ Phone Help", callback_data="am_phone_help")],
            [InlineKeyboardButton(text="🔙 Back to Account Management", callback_data="account_management")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_code_input_keyboard(self) -> InlineKeyboardMarkup:
        """Get code input keyboard"""
        buttons = [
            [InlineKeyboardButton(text="🔄 Resend Code", callback_data="am_resend_code")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="account_management")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_password_input_keyboard(self) -> InlineKeyboardMarkup:
        """Get password input keyboard"""
        buttons = [
            [InlineKeyboardButton(text="❓ Password Help", callback_data="am_password_help")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="account_management")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_retry_code_keyboard(self) -> InlineKeyboardMarkup:
        """Get retry code keyboard"""
        buttons = [
            [InlineKeyboardButton(text="🔄 Resend Code", callback_data="am_resend_code")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="account_management")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_retry_password_keyboard(self) -> InlineKeyboardMarkup:
        """Get retry password keyboard"""
        buttons = [
            [InlineKeyboardButton(text="❓ Password Help", callback_data="am_password_help")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="account_management")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_account_added_keyboard(self) -> InlineKeyboardMarkup:
        """Get account added keyboard"""
        buttons = [
            [
                InlineKeyboardButton(text="📱 View Accounts", callback_data="am_list_accounts"),
                InlineKeyboardButton(text="➕ Add Another", callback_data="am_add_account")
            ],
            [
                InlineKeyboardButton(text="🚀 Start Boosting", callback_data="view_manager"),
                InlineKeyboardButton(text="🔙 Back to Menu", callback_data="refresh_main")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def _get_restart_keyboard(self) -> InlineKeyboardMarkup:
        """Get restart keyboard"""
        buttons = [
            [InlineKeyboardButton(text="🔄 Start Over", callback_data="am_add_account")],
            [InlineKeyboardButton(text="🔙 Back to Account Management", callback_data="account_management")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    async def shutdown(self):
        """Shutdown account management handler"""
        try:
            if hasattr(self.bot_core, 'shutdown'):
                await self.bot_core.shutdown()
            
            # Clear pending verifications
            self._pending_verifications.clear()
            
            logger.info("✅ Account management handler shut down")
        except Exception as e:
            logger.error(f"Error shutting down account management handler: {e}")
