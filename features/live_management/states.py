"""
Live Management FSM States
Finite State Machine states for live stream management operations
"""

from aiogram.fsm.state import State, StatesGroup


class LiveManagementStates(StatesGroup):
    """FSM states for live management operations"""
    
    # Auto join setup states
    setting_up_auto_join = State()
    selecting_auto_channels = State()
    configuring_auto_timing = State()
    setting_auto_conditions = State()
    
    # Manual join states
    waiting_for_stream_link = State()
    selecting_accounts_for_join = State()
    configuring_join_settings = State()
    confirming_manual_join = State()
    
    # Stream monitoring states
    configuring_monitor_settings = State()
    setting_alert_conditions = State()
    customizing_monitor_view = State()
    
    # Voice settings states
    configuring_audio_settings = State()
    setting_privacy_options = State()
    configuring_detection_params = State()
    setting_performance_options = State()


class AutoJoinStates(StatesGroup):
    """FSM states specific to auto join functionality"""
    
    # Channel selection
    selecting_channels_for_auto = State()
    configuring_channel_priorities = State()
    setting_channel_specific_rules = State()
    
    # Timing configuration
    setting_join_delays = State()
    configuring_peak_hours = State()
    setting_blackout_periods = State()
    
    # Account management
    assigning_accounts_to_channels = State()
    configuring_account_rotation = State()
    setting_account_limits = State()
    
    # Conditions and filters
    setting_participant_thresholds = State()
    configuring_stream_filters = State()
    setting_quality_requirements = State()


class ManualJoinStates(StatesGroup):
    """FSM states specific to manual join operations"""
    
    # Stream identification
    entering_stream_link = State()
    scanning_for_streams = State()
    selecting_detected_stream = State()
    
    # Join configuration
    selecting_join_accounts = State()
    setting_join_timing = State()
    configuring_join_behavior = State()
    
    # Advanced options
    setting_custom_parameters = State()
    configuring_leave_conditions = State()
    setting_interaction_rules = State()


class StreamMonitorStates(StatesGroup):
    """FSM states for stream monitoring"""
    
    # Monitor configuration
    setting_monitor_channels = State()
    configuring_check_intervals = State()
    setting_detection_sensitivity = State()
    
    # Alert configuration
    setting_alert_types = State()
    configuring_notification_methods = State()
    setting_alert_thresholds = State()
    
    # Data management
    configuring_data_retention = State()
    setting_export_preferences = State()
    configuring_analytics_options = State()


class VoiceSettingsStates(StatesGroup):
    """FSM states for voice and audio settings"""
    
    # Audio configuration
    setting_audio_quality = State()
    configuring_microphone_settings = State()
    setting_speaker_options = State()
    
    # Privacy configuration
    setting_anonymity_level = State()
    configuring_identity_protection = State()
    setting_interaction_limits = State()
    
    # Performance optimization
    setting_connection_quality = State()
    configuring_bandwidth_limits = State()
    setting_resource_usage = State()
