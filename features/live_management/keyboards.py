"""
Live Management Keyboards
Inline keyboards for live stream management operations
"""

from typing import List, Dict, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


class LiveManagementKeyboards:
    """Keyboards for live management"""
    
    def get_auto_join_keyboard(self, has_enabled: bool) -> InlineKeyboardMarkup:
        """Get auto join keyboard"""
        buttons = [
            [
                InlineKeyboardButton(text="⚙️ Setup Auto Join", callback_data="aj_setup"),
                InlineKeyboardButton(text="📋 Manage Channels", callback_data="aj_manage_channels")
            ],
            [
                InlineKeyboardButton(text="📊 Join Statistics", callback_data="aj_statistics"),
                InlineKeyboardButton(text="⏰ Schedule Settings", callback_data="aj_schedule")
            ]
        ]
        
        if has_enabled:
            buttons.append([
                InlineKeyboardButton(text="⏸️ Pause Auto Join", callback_data="aj_pause"),
                InlineKeyboardButton(text="🔄 Resume Auto Join", callback_data="aj_resume")
            ])
        
        buttons.extend([
            [InlineKeyboardButton(text="⚙️ Advanced Settings", callback_data="aj_advanced")],
            [InlineKeyboardButton(text="🔙 Back to Live Management", callback_data="live_management")]
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def get_manual_join_keyboard(self, has_active_streams: bool) -> InlineKeyboardMarkup:
        """Get manual join keyboard"""
        buttons = [
            [
                InlineKeyboardButton(text="🔗 Join by Link", callback_data="mj_by_link"),
                InlineKeyboardButton(text="📋 Select Channel", callback_data="mj_select_channel")
            ]
        ]
        
        if has_active_streams:
            buttons.append([
                InlineKeyboardButton(text="🎙️ Join Active Stream", callback_data="mj_join_active"),
                InlineKeyboardButton(text="👁️ View Active Streams", callback_data="mj_view_active")
            ])
        
        buttons.extend([
            [
                InlineKeyboardButton(text="🔍 Scan for Streams", callback_data="mj_scan"),
                InlineKeyboardButton(text="⚙️ Join Settings", callback_data="mj_settings")
            ],
            [
                InlineKeyboardButton(text="📊 Join History", callback_data="mj_history"),
                InlineKeyboardButton(text="🚨 Stream Alerts", callback_data="mj_alerts")
            ],
            [
                InlineKeyboardButton(text="🔙 Back to Live Management", callback_data="live_management")
            ]
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def get_monitor_keyboard(self) -> InlineKeyboardMarkup:
        """Get monitor keyboard"""
        buttons = [
            [
                InlineKeyboardButton(text="🔄 Refresh Monitor", callback_data="lm_monitor"),
                InlineKeyboardButton(text="⚡ Real-time View", callback_data="lm_realtime")
            ],
            [
                InlineKeyboardButton(text="📊 Detailed Analytics", callback_data="lm_analytics"),
                InlineKeyboardButton(text="📈 Performance Charts", callback_data="lm_charts")
            ],
            [
                InlineKeyboardButton(text="🔍 Stream Scanner", callback_data="lm_scanner"),
                InlineKeyboardButton(text="🚨 Alert Settings", callback_data="lm_alerts")
            ],
            [
                InlineKeyboardButton(text="📤 Export Report", callback_data="lm_export"),
                InlineKeyboardButton(text="⚙️ Monitor Settings", callback_data="lm_monitor_settings")
            ],
            [
                InlineKeyboardButton(text="🔙 Back to Live Management", callback_data="live_management")
            ]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def get_voice_settings_keyboard(self) -> InlineKeyboardMarkup:
        """Get voice settings keyboard"""
        buttons = [
            [
                InlineKeyboardButton(text="🤖 Auto Join Settings", callback_data="vs_auto_join"),
                InlineKeyboardButton(text="🎙️ Audio Settings", callback_data="vs_audio")
            ],
            [
                InlineKeyboardButton(text="🔍 Detection Settings", callback_data="vs_detection"),
                InlineKeyboardButton(text="🚨 Alert Settings", callback_data="vs_alerts")
            ],
            [
                InlineKeyboardButton(text="🔐 Privacy Settings", callback_data="vs_privacy"),
                InlineKeyboardButton(text="⚡ Performance Settings", callback_data="vs_performance")
            ],
            [
                InlineKeyboardButton(text="💾 Save Settings", callback_data="vs_save"),
                InlineKeyboardButton(text="🔄 Reset to Default", callback_data="vs_reset")
            ],
            [
                InlineKeyboardButton(text="🔙 Back to Live Management", callback_data="live_management")
            ]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def get_no_channels_keyboard(self) -> InlineKeyboardMarkup:
        """Get no channels keyboard"""
        buttons = [
            [InlineKeyboardButton(text="➕ Add Channel", callback_data="channel_management")],
            [InlineKeyboardButton(text="🔙 Back to Live Management", callback_data="live_management")]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def get_stream_details_keyboard(self, stream_id: int) -> InlineKeyboardMarkup:
        """Get stream details keyboard"""
        buttons = [
            [
                InlineKeyboardButton(text="🚀 Join Stream", callback_data=f"lm_join_{stream_id}"),
                InlineKeyboardButton(text="👥 View Participants", callback_data=f"lm_participants_{stream_id}")
            ],
            [
                InlineKeyboardButton(text="📊 Stream Stats", callback_data=f"lm_stats_{stream_id}"),
                InlineKeyboardButton(text="🔔 Set Alert", callback_data=f"lm_alert_{stream_id}")
            ],
            [
                InlineKeyboardButton(text="📤 Share Stream", callback_data=f"lm_share_{stream_id}"),
                InlineKeyboardButton(text="⚙️ Stream Settings", callback_data=f"lm_stream_settings_{stream_id}")
            ],
            [
                InlineKeyboardButton(text="🔙 Back to Monitor", callback_data="lm_monitor")
            ]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def get_join_confirmation_keyboard(self, stream_id: int) -> InlineKeyboardMarkup:
        """Get join confirmation keyboard"""
        buttons = [
            [
                InlineKeyboardButton(text="✅ Confirm Join", callback_data=f"lm_confirm_join_{stream_id}"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="lm_monitor")
            ],
            [
                InlineKeyboardButton(text="⚙️ Join Settings", callback_data=f"lm_join_settings_{stream_id}"),
                InlineKeyboardButton(text="📱 Select Accounts", callback_data=f"lm_select_accounts_{stream_id}")
            ]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def get_stream_history_keyboard(self) -> InlineKeyboardMarkup:
        """Get stream history keyboard"""
        buttons = [
            [
                InlineKeyboardButton(text="📊 Today's Streams", callback_data="lm_history_today"),
                InlineKeyboardButton(text="📈 This Week", callback_data="lm_history_week")
            ],
            [
                InlineKeyboardButton(text="📅 This Month", callback_data="lm_history_month"),
                InlineKeyboardButton(text="📋 All Time", callback_data="lm_history_all")
            ],
            [
                InlineKeyboardButton(text="🎯 Filter by Channel", callback_data="lm_filter_channel"),
                InlineKeyboardButton(text="🔍 Search Streams", callback_data="lm_search_streams")
            ],
            [
                InlineKeyboardButton(text="📤 Export History", callback_data="lm_export_history"),
                InlineKeyboardButton(text="📊 Statistics", callback_data="lm_history_stats")
            ],
            [
                InlineKeyboardButton(text="🔙 Back to Live Management", callback_data="live_management")
            ]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def get_auto_join_setup_keyboard(self) -> InlineKeyboardMarkup:
        """Get auto join setup keyboard"""
        buttons = [
            [
                InlineKeyboardButton(text="📋 Select Channels", callback_data="aj_select_channels"),
                InlineKeyboardButton(text="⏰ Set Timing", callback_data="aj_set_timing")
            ],
            [
                InlineKeyboardButton(text="📱 Choose Accounts", callback_data="aj_choose_accounts"),
                InlineKeyboardButton(text="🎯 Set Conditions", callback_data="aj_set_conditions")
            ],
            [
                InlineKeyboardButton(text="✅ Enable Auto Join", callback_data="aj_enable"),
                InlineKeyboardButton(text="🧪 Test Setup", callback_data="aj_test")
            ],
            [
                InlineKeyboardButton(text="🔙 Back to Auto Join", callback_data="lm_auto_join")
            ]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def get_account_selection_keyboard(self, accounts: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
        """Get account selection keyboard"""
        buttons = []
        
        # Add account buttons (max 6)
        for account in accounts[:6]:
            status_emoji = "🟢" if account['is_active'] else "🔴"
            buttons.append([
                InlineKeyboardButton(
                    text=f"{status_emoji} {account['phone_number']}",
                    callback_data=f"lm_account_{account['id']}"
                )
            ])
        
        # Control buttons
        buttons.extend([
            [
                InlineKeyboardButton(text="✅ Select All", callback_data="lm_select_all_accounts"),
                InlineKeyboardButton(text="❌ Deselect All", callback_data="lm_deselect_all_accounts")
            ],
            [
                InlineKeyboardButton(text="🎲 Random Selection", callback_data="lm_random_accounts"),
                InlineKeyboardButton(text="💚 Healthy Only", callback_data="lm_healthy_accounts")
            ],
            [
                InlineKeyboardButton(text="✅ Confirm Selection", callback_data="lm_confirm_accounts"),
                InlineKeyboardButton(text="🔙 Back", callback_data="lm_manual_join")
            ]
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def get_stream_scanner_keyboard(self) -> InlineKeyboardMarkup:
        """Get stream scanner keyboard"""
        buttons = [
            [
                InlineKeyboardButton(text="🔍 Quick Scan", callback_data="ls_quick_scan"),
                InlineKeyboardButton(text="🔬 Deep Scan", callback_data="ls_deep_scan")
            ],
            [
                InlineKeyboardButton(text="⚡ Real-time Scan", callback_data="ls_realtime_scan"),
                InlineKeyboardButton(text="📋 Scan All Channels", callback_data="ls_scan_all")
            ],
            [
                InlineKeyboardButton(text="🎯 Custom Scan", callback_data="ls_custom_scan"),
                InlineKeyboardButton(text="📊 Scan Results", callback_data="ls_scan_results")
            ],
            [
                InlineKeyboardButton(text="⚙️ Scanner Settings", callback_data="ls_scanner_settings"),
                InlineKeyboardButton(text="📤 Export Results", callback_data="ls_export_scan")
            ],
            [
                InlineKeyboardButton(text="🔙 Back to Monitor", callback_data="lm_monitor")
            ]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
