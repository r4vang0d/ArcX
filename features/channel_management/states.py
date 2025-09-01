"""
Channel Management FSM States
Finite State Machine states for channel management operations
"""

from aiogram.fsm.state import State, StatesGroup


class ChannelManagementStates(StatesGroup):
    """FSM states for channel management"""
    
    # Adding channel states
    waiting_for_channel = State()
    waiting_for_channel_confirmation = State()
    waiting_for_invite_link = State()
    
    # Editing channel states
    editing_channel_title = State()
    editing_channel_description = State()
    editing_channel_settings = State()
    
    # Channel validation states
    validating_permissions = State()
    confirming_channel_access = State()
    
    # Batch operations states
    batch_adding_channels = State()
    waiting_for_channel_list = State()
    
    # Settings configuration states
    configuring_boost_settings = State()
    configuring_notification_settings = State()
    configuring_analytics_settings = State()


class ChannelSettingsStates(StatesGroup):
    """FSM states for channel settings configuration"""
    
    # General settings
    updating_channel_info = State()
    configuring_auto_refresh = State()
    
    # Boost settings
    setting_default_boost_amount = State()
    setting_boost_schedule = State()
    setting_boost_accounts = State()
    
    # Reaction settings
    configuring_reaction_emojis = State()
    setting_reaction_timing = State()
    setting_reaction_frequency = State()
    
    # Analytics settings
    configuring_analytics_frequency = State()
    setting_report_schedule = State()
    configuring_alert_thresholds = State()
    
    # Notification settings
    setting_notification_types = State()
    configuring_notification_channels = State()
    setting_quiet_hours = State()
