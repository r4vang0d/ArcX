"""
Channel Management Keyboards
Inline keyboards for channel management operations
"""

from typing import List, Dict, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


class ChannelManagementKeyboards:
    """Keyboards for channel management"""
    
    def get_add_channel_keyboard(self) -> InlineKeyboardMarkup:
        """Get keyboard for add channel start"""
        buttons = [
            [InlineKeyboardButton(text="📝 Enter Channel Info", callback_data="cm_input_ready")],
            [InlineKeyboardButton(text="❓ Help", callback_data="cm_add_help")],
            [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="refresh_main")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def get_channel_added_keyboard(self) -> InlineKeyboardMarkup:
        """Get keyboard after channel is successfully added"""
        buttons = [
            [InlineKeyboardButton(text="🚀 Start Boosting", callback_data="view_manager")],
            [InlineKeyboardButton(text="📋 View Channels", callback_data="cm_list_channels")],
            [InlineKeyboardButton(text="➕ Add Another", callback_data="cm_add_channel")],
            [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="refresh_main")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def get_add_channel_retry_keyboard(self) -> InlineKeyboardMarkup:
        """Get keyboard for retry adding channel"""
        buttons = [
            [InlineKeyboardButton(text="🔄 Try Again", callback_data="cm_add_channel")],
            [InlineKeyboardButton(text="❓ Get Help", callback_data="cm_add_help")],
            [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="refresh_main")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def get_no_channels_keyboard(self) -> InlineKeyboardMarkup:
        """Get keyboard when user has no channels"""
        buttons = [
            [InlineKeyboardButton(text="➕ Add First Channel", callback_data="cm_add_channel")],
            [InlineKeyboardButton(text="❓ How to Add Channels", callback_data="cm_add_help")],
            [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="refresh_main")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def get_channels_list_keyboard(self, channels: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
        """Get keyboard for channels list"""
        buttons = []
        
        # Add channel action buttons (max 5)
        for channel in channels[:5]:
            status = "🟢" if channel['is_active'] else "🔴"
            buttons.append([
                InlineKeyboardButton(
                    text=f"{status} {channel['title'][:30]}",
                    callback_data=f"cm_channel_{channel['id']}"
                )
            ])
        
        # Add control buttons
        control_buttons = []
        if len(channels) > 5:
            control_buttons.append(
                InlineKeyboardButton(text="📄 View All", callback_data="cm_view_all_channels")
            )
        
        control_buttons.extend([
            InlineKeyboardButton(text="➕ Add Channel", callback_data="cm_add_channel"),
            InlineKeyboardButton(text="⚙️ Settings", callback_data="cm_settings")
        ])
        
        if control_buttons:
            # Split control buttons into rows of 2
            for i in range(0, len(control_buttons), 2):
                buttons.append(control_buttons[i:i+2])
        
        # Back button
        buttons.append([
            InlineKeyboardButton(text="🔙 Back to Menu", callback_data="refresh_main")
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def get_channel_actions_keyboard(self, channel_id: int) -> InlineKeyboardMarkup:
        """Get keyboard for individual channel actions"""
        buttons = [
            [
                InlineKeyboardButton(text="🚀 Boost Views", callback_data=f"vm_boost_channel_{channel_id}"),
                InlineKeyboardButton(text="📊 Analytics", callback_data=f"an_channel_{channel_id}")
            ],
            [
                InlineKeyboardButton(text="🎭 Reactions", callback_data=f"er_channel_{channel_id}"),
                InlineKeyboardButton(text="👁️ Monitor", callback_data=f"vm_monitor_{channel_id}")
            ],
            [
                InlineKeyboardButton(text="✏️ Edit", callback_data=f"cm_edit_{channel_id}"),
                InlineKeyboardButton(text="🗑️ Delete", callback_data=f"cm_delete_{channel_id}")
            ],
            [
                InlineKeyboardButton(text="🔄 Refresh Info", callback_data=f"cm_refresh_{channel_id}"),
                InlineKeyboardButton(text="⚙️ Settings", callback_data=f"cm_settings_{channel_id}")
            ],
            [
                InlineKeyboardButton(text="🔙 Back to Channels", callback_data="cm_list_channels")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def get_settings_channels_keyboard(self, channels: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
        """Get keyboard for selecting channel to configure"""
        buttons = []
        
        # Add channels (max 8)
        for channel in channels[:8]:
            status = "🟢" if channel['is_active'] else "🔴"
            buttons.append([
                InlineKeyboardButton(
                    text=f"{status} {channel['title'][:35]}",
                    callback_data=f"cm_settings_{channel['id']}"
                )
            ])
        
        # Control buttons
        if len(channels) > 8:
            buttons.append([
                InlineKeyboardButton(text="📄 More Channels", callback_data="cm_settings_more")
            ])
        
        buttons.extend([
            [InlineKeyboardButton(text="⚙️ Global Settings", callback_data="cm_global_settings")],
            [InlineKeyboardButton(text="🔙 Back to Channels", callback_data="cm_list_channels")]
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def get_delete_confirmation_keyboard(self, channel_id: int) -> InlineKeyboardMarkup:
        """Get keyboard for delete confirmation"""
        buttons = [
            [
                InlineKeyboardButton(text="✅ Yes, Delete", callback_data=f"cm_confirm_delete_{channel_id}"),
                InlineKeyboardButton(text="❌ Cancel", callback_data=f"cm_channel_{channel_id}")
            ],
            [
                InlineKeyboardButton(text="🔙 Back to Channel", callback_data=f"cm_channel_{channel_id}")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def get_edit_channel_keyboard(self, channel_id: int) -> InlineKeyboardMarkup:
        """Get keyboard for editing channel"""
        buttons = [
            [
                InlineKeyboardButton(text="📝 Update Info", callback_data=f"cm_edit_info_{channel_id}"),
                InlineKeyboardButton(text="🔄 Refresh Data", callback_data=f"cm_refresh_{channel_id}")
            ],
            [
                InlineKeyboardButton(text="🚀 Boost Settings", callback_data=f"cm_edit_boost_{channel_id}"),
                InlineKeyboardButton(text="🎭 Reaction Settings", callback_data=f"cm_edit_reactions_{channel_id}")
            ],
            [
                InlineKeyboardButton(text="📊 Analytics Settings", callback_data=f"cm_edit_analytics_{channel_id}"),
                InlineKeyboardButton(text="🔔 Notifications", callback_data=f"cm_edit_notifications_{channel_id}")
            ],
            [
                InlineKeyboardButton(text="🔙 Back to Channel", callback_data=f"cm_channel_{channel_id}")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def get_back_to_channel_keyboard(self, channel_id: int) -> InlineKeyboardMarkup:
        """Get keyboard to go back to channel"""
        buttons = [
            [InlineKeyboardButton(text="🔙 Back to Channel", callback_data=f"cm_channel_{channel_id}")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def get_back_to_menu_keyboard(self) -> InlineKeyboardMarkup:
        """Get keyboard to go back to main menu"""
        buttons = [
            [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="refresh_main")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def get_channel_settings_keyboard(self, channel_id: int) -> InlineKeyboardMarkup:
        """Get keyboard for channel-specific settings"""
        buttons = [
            [
                InlineKeyboardButton(text="🚀 Default Boost Settings", callback_data=f"cm_set_boost_{channel_id}"),
                InlineKeyboardButton(text="⏰ Boost Schedule", callback_data=f"cm_set_schedule_{channel_id}")
            ],
            [
                InlineKeyboardButton(text="🎭 Reaction Config", callback_data=f"cm_set_reactions_{channel_id}"),
                InlineKeyboardButton(text="📱 Account Assignment", callback_data=f"cm_set_accounts_{channel_id}")
            ],
            [
                InlineKeyboardButton(text="📊 Analytics Config", callback_data=f"cm_set_analytics_{channel_id}"),
                InlineKeyboardButton(text="🔔 Alert Settings", callback_data=f"cm_set_alerts_{channel_id}")
            ],
            [
                InlineKeyboardButton(text="💾 Save Settings", callback_data=f"cm_save_settings_{channel_id}"),
                InlineKeyboardButton(text="🔄 Reset to Default", callback_data=f"cm_reset_settings_{channel_id}")
            ],
            [
                InlineKeyboardButton(text="🔙 Back to Channel", callback_data=f"cm_channel_{channel_id}")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def get_batch_operations_keyboard(self) -> InlineKeyboardMarkup:
        """Get keyboard for batch operations on channels"""
        buttons = [
            [
                InlineKeyboardButton(text="📥 Bulk Add Channels", callback_data="cm_bulk_add"),
                InlineKeyboardButton(text="🔄 Refresh All", callback_data="cm_refresh_all")
            ],
            [
                InlineKeyboardButton(text="⚙️ Bulk Settings", callback_data="cm_bulk_settings"),
                InlineKeyboardButton(text="📊 Export Data", callback_data="cm_export_data")
            ],
            [
                InlineKeyboardButton(text="🗑️ Bulk Delete", callback_data="cm_bulk_delete"),
                InlineKeyboardButton(text="🔄 Bulk Status", callback_data="cm_bulk_status")
            ],
            [
                InlineKeyboardButton(text="🔙 Back to Channels", callback_data="cm_list_channels")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
