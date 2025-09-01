"""
Time Parser Utility
Handles parsing and formatting of time expressions for boost scheduling
"""

import re
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import pytz

logger = logging.getLogger(__name__)


class TimeParser:
    """Utility for parsing time expressions and scheduling"""
    
    def __init__(self):
        self.timezone_map = {
            'utc': 'UTC',
            'est': 'America/New_York',
            'pst': 'America/Los_Angeles',
            'cet': 'Europe/Berlin',
            'gmt': 'GMT',
            'msk': 'Europe/Moscow'
        }
        
        self.time_units = {
            'seconds': 1,
            'minutes': 60,
            'hours': 3600,
            'days': 86400,
            'weeks': 604800
        }
    
    def parse_time_expression(self, expression: str, user_timezone: str = 'UTC') -> Optional[datetime]:
        """Parse various time expressions into datetime objects"""
        try:
            expr = expression.lower().strip()
            now = datetime.now()
            
            # Immediate execution
            if expr in ['now', 'immediately', 'asap']:
                return now
            
            # Relative time expressions
            if expr.startswith('in '):
                return self._parse_relative_time(expr, now)
            
            # Specific time today
            if expr.startswith('at '):
                return self._parse_specific_time(expr, now)
            
            # Named times
            if expr in ['tomorrow', 'next day']:
                return now.replace(hour=12, minute=0, second=0, microsecond=0) + timedelta(days=1)
            
            if expr in ['tonight', 'this evening']:
                return now.replace(hour=20, minute=0, second=0, microsecond=0)
            
            if expr in ['morning', 'tomorrow morning']:
                days_add = 1 if 'tomorrow' in expr or now.hour > 10 else 0
                return now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=days_add)
            
            # Day of week
            weekday_result = self._parse_weekday(expr, now)
            if weekday_result:
                return weekday_result
            
            # Date formats
            date_result = self._parse_date_format(expr, user_timezone)
            if date_result:
                return date_result
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing time expression '{expression}': {e}")
            return None
    
    def _parse_relative_time(self, expr: str, base_time: datetime) -> Optional[datetime]:
        """Parse relative time expressions like 'in 2 hours'"""
        try:
            # Remove 'in ' prefix
            time_part = expr[3:].strip()
            
            # Match patterns like "2 hours", "30 minutes", "1 day"
            pattern = r'(\d+)\s*(second|minute|hour|day|week)s?'
            match = re.match(pattern, time_part)
            
            if match:
                amount = int(match.group(1))
                unit = match.group(2) + 's'  # Normalize to plural
                
                if unit in self.time_units:
                    seconds_to_add = amount * self.time_units[unit]
                    return base_time + timedelta(seconds=seconds_to_add)
            
            # Handle compound expressions like "1 hour 30 minutes"
            compound_pattern = r'(\d+)\s*hours?\s*(\d+)\s*minutes?'
            compound_match = re.match(compound_pattern, time_part)
            
            if compound_match:
                hours = int(compound_match.group(1))
                minutes = int(compound_match.group(2))
                return base_time + timedelta(hours=hours, minutes=minutes)
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing relative time '{expr}': {e}")
            return None
    
    def _parse_specific_time(self, expr: str, base_time: datetime) -> Optional[datetime]:
        """Parse specific time expressions like 'at 15:30'"""
        try:
            # Remove 'at ' prefix
            time_part = expr[3:].strip()
            
            # Match HH:MM format
            time_pattern = r'(\d{1,2}):(\d{2})'
            match = re.match(time_pattern, time_part)
            
            if match:
                hour = int(match.group(1))
                minute = int(match.group(2))
                
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    target_time = base_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    
                    # If the time has passed today, schedule for tomorrow
                    if target_time <= base_time:
                        target_time += timedelta(days=1)
                    
                    return target_time
            
            # Match 12-hour format with AM/PM
            ampm_pattern = r'(\d{1,2}):?(\d{2})?\s*(am|pm)'
            ampm_match = re.match(ampm_pattern, time_part)
            
            if ampm_match:
                hour = int(ampm_match.group(1))
                minute = int(ampm_match.group(2)) if ampm_match.group(2) else 0
                ampm = ampm_match.group(3)
                
                # Convert to 24-hour format
                if ampm == 'pm' and hour != 12:
                    hour += 12
                elif ampm == 'am' and hour == 12:
                    hour = 0
                
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    target_time = base_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    
                    if target_time <= base_time:
                        target_time += timedelta(days=1)
                    
                    return target_time
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing specific time '{expr}': {e}")
            return None
    
    def _parse_weekday(self, expr: str, base_time: datetime) -> Optional[datetime]:
        """Parse weekday expressions like 'monday', 'next friday'"""
        try:
            weekdays = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                'friday': 4, 'saturday': 5, 'sunday': 6
            }
            
            # Handle "next [weekday]" or just "[weekday]"
            next_prefix = expr.startswith('next ')
            weekday_name = expr.replace('next ', '').strip()
            
            if weekday_name in weekdays:
                target_weekday = weekdays[weekday_name]
                current_weekday = base_time.weekday()
                
                days_ahead = target_weekday - current_weekday
                
                # If it's the same day but later in the day, or "next" is specified
                if days_ahead <= 0 or next_prefix:
                    days_ahead += 7
                
                target_date = base_time + timedelta(days=days_ahead)
                return target_date.replace(hour=12, minute=0, second=0, microsecond=0)
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing weekday '{expr}': {e}")
            return None
    
    def _parse_date_format(self, expr: str, user_timezone: str) -> Optional[datetime]:
        """Parse date formats like '2024-01-15 14:30'"""
        try:
            # ISO format: YYYY-MM-DD HH:MM
            iso_pattern = r'(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2}):(\d{2})'
            iso_match = re.match(iso_pattern, expr)
            
            if iso_match:
                year = int(iso_match.group(1))
                month = int(iso_match.group(2))
                day = int(iso_match.group(3))
                hour = int(iso_match.group(4))
                minute = int(iso_match.group(5))
                
                return datetime(year, month, day, hour, minute)
            
            # Date only: YYYY-MM-DD (default to noon)
            date_pattern = r'(\d{4})-(\d{2})-(\d{2})$'
            date_match = re.match(date_pattern, expr)
            
            if date_match:
                year = int(date_match.group(1))
                month = int(date_match.group(2))
                day = int(date_match.group(3))
                
                return datetime(year, month, day, 12, 0)
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing date format '{expr}': {e}")
            return None
    
    def format_duration(self, start_time: datetime, end_time: datetime) -> str:
        """Format duration between two times in human-readable format"""
        try:
            delta = end_time - start_time
            
            if delta.days > 0:
                return f"{delta.days} day{'s' if delta.days != 1 else ''}"
            
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60
            
            if hours > 0:
                if minutes > 0:
                    return f"{hours}h {minutes}m"
                else:
                    return f"{hours} hour{'s' if hours != 1 else ''}"
            elif minutes > 0:
                return f"{minutes} minute{'s' if minutes != 1 else ''}"
            else:
                return "less than a minute"
                
        except Exception as e:
            logger.error(f"Error formatting duration: {e}")
            return "unknown duration"
    
    def format_time_until(self, target_time: datetime) -> str:
        """Format time remaining until target time"""
        try:
            now = datetime.now()
            
            if target_time <= now:
                return "now"
            
            return self.format_duration(now, target_time)
            
        except Exception as e:
            logger.error(f"Error formatting time until: {e}")
            return "unknown"
    
    def get_timezone_offset(self, timezone_name: str) -> str:
        """Get timezone offset string"""
        try:
            # Map common abbreviations
            tz_name = self.timezone_map.get(timezone_name.lower(), timezone_name)
            
            tz = pytz.timezone(tz_name)
            now = datetime.now(tz)
            offset = now.strftime('%z')
            
            # Format as +HH:MM
            if len(offset) == 5:
                return f"{offset[:3]}:{offset[3:]}"
            
            return offset
            
        except Exception as e:
            logger.error(f"Error getting timezone offset for '{timezone_name}': {e}")
            return "+00:00"
    
    def validate_time_expression(self, expression: str) -> Dict[str, Any]:
        """Validate a time expression and return parsed result with validation info"""
        try:
            parsed_time = self.parse_time_expression(expression)
            
            if parsed_time is None:
                return {
                    'valid': False,
                    'error': 'Unable to parse time expression',
                    'suggestions': self._get_format_suggestions()
                }
            
            # Check if time is in the past
            if parsed_time <= datetime.now():
                return {
                    'valid': False,
                    'error': 'Time must be in the future',
                    'parsed_time': parsed_time
                }
            
            # Check if time is too far in the future (e.g., more than 1 year)
            if parsed_time > datetime.now() + timedelta(days=365):
                return {
                    'valid': False,
                    'error': 'Time cannot be more than 1 year in the future',
                    'parsed_time': parsed_time
                }
            
            return {
                'valid': True,
                'parsed_time': parsed_time,
                'formatted': parsed_time.strftime('%Y-%m-%d %H:%M:%S'),
                'time_until': self.format_time_until(parsed_time)
            }
            
        except Exception as e:
            logger.error(f"Error validating time expression '{expression}': {e}")
            return {
                'valid': False,
                'error': f'Validation error: {str(e)}',
                'suggestions': self._get_format_suggestions()
            }
    
    def _get_format_suggestions(self) -> List[str]:
        """Get list of supported time format suggestions"""
        return [
            "now, immediately",
            "in 30 minutes, in 2 hours, in 1 day",
            "at 15:30, at 9:00 pm",
            "tomorrow, tonight, tomorrow morning",
            "monday, next friday",
            "2024-01-15 14:30"
        ]
    
    def get_peak_hours(self, timezone: str = 'UTC') -> List[Dict[str, Any]]:
        """Get typical peak hours for content engagement"""
        try:
            # General peak hours for different regions
            peak_periods = [
                {'start': 8, 'end': 10, 'description': 'Morning commute'},
                {'start': 12, 'end': 14, 'description': 'Lunch break'},
                {'start': 17, 'end': 21, 'description': 'Evening prime time'}
            ]
            
            return peak_periods
            
        except Exception as e:
            logger.error(f"Error getting peak hours: {e}")
            return []
    
    def suggest_optimal_times(self, count: int = 3) -> List[Dict[str, Any]]:
        """Suggest optimal times for boosting based on general best practices"""
        try:
            now = datetime.now()
            suggestions = []
            
            # Next peak hour today or tomorrow
            peak_hours = [9, 13, 19]  # 9 AM, 1 PM, 7 PM
            
            for hour in peak_hours:
                target_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
                
                # If past this hour today, schedule for tomorrow
                if target_time <= now:
                    target_time += timedelta(days=1)
                
                suggestions.append({
                    'time': target_time,
                    'formatted': target_time.strftime('%Y-%m-%d %H:%M'),
                    'description': f"Peak hour ({hour}:00)",
                    'time_until': self.format_time_until(target_time)
                })
                
                if len(suggestions) >= count:
                    break
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Error suggesting optimal times: {e}")
            return []
