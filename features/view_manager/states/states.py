"""
View Manager FSM States
Finite State Machine states for view boosting operations
"""

from aiogram.fsm.state import State, StatesGroup


class ViewBoostStates(StatesGroup):
    """FSM states for view boosting operations"""
    
    # Manual boost states
    waiting_for_message_link = State()
    waiting_for_boost_params = State()
    confirming_boost_start = State()
    selecting_boost_accounts = State()
    
    # Auto boost setup states
    configuring_auto_boost = State()
    setting_auto_channels = State()
    setting_auto_parameters = State()
    confirming_auto_setup = State()
    
    # Scheduling states
    setting_schedule_time = State()
    setting_schedule_repeat = State()
    configuring_schedule_params = State()
    confirming_schedule = State()
    
    # Campaign management states
    viewing_campaign_details = State()
    editing_campaign_params = State()
    confirming_campaign_changes = State()
    
    # Batch operations states
    selecting_multiple_channels = State()
    setting_batch_parameters = State()
    confirming_batch_boost = State()
    
    # Settings configuration states
    configuring_boost_settings = State()
    setting_timing_preferences = State()
    configuring_account_preferences = State()
    setting_notification_preferences = State()


class AutoBoostStates(StatesGroup):
    """FSM states specific to auto boosting"""
    
    # Channel selection and configuration
    selecting_auto_channels = State()
    configuring_channel_settings = State()
    setting_channel_boost_params = State()
    
    # Detection and monitoring settings
    setting_detection_interval = State()
    configuring_post_filters = State()
    setting_boost_triggers = State()
    
    # Advanced auto boost settings
    configuring_smart_timing = State()
    setting_account_rotation = State()
    configuring_rate_limits = State()
    setting_retry_behavior = State()
    
    # Auto boost monitoring
    reviewing_auto_performance = State()
    adjusting_auto_parameters = State()


class ScheduleStates(StatesGroup):
    """FSM states for boost scheduling"""
    
    # Time and date settings
    setting_start_time = State()
    setting_end_time = State()
    selecting_timezone = State()
    setting_repeat_pattern = State()
    
    # Schedule configuration
    configuring_schedule_params = State()
    setting_schedule_channels = State()
    setting_schedule_accounts = State()
    
    # Schedule management
    viewing_schedule_calendar = State()
    editing_scheduled_boost = State()
    confirming_schedule_changes = State()
    
    # Advanced scheduling
    setting_conditional_triggers = State()
    configuring_peak_time_optimization = State()
    setting_holiday_exceptions = State()


class CampaignStates(StatesGroup):
    """FSM states for campaign management"""
    
    # Campaign creation
    creating_campaign = State()
    setting_campaign_name = State()
    configuring_campaign_targets = State()
    setting_campaign_duration = State()
    
    # Campaign monitoring
    viewing_campaign_analytics = State()
    adjusting_campaign_parameters = State()
    setting_campaign_alerts = State()
    
    # Campaign collaboration
    sharing_campaign_access = State()
    setting_campaign_permissions = State()
    configuring_team_notifications = State()
