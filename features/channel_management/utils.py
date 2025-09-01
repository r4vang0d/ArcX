"""
Channel Management Utilities
Helper functions for channel validation and processing
"""

import re
import logging
from typing import Dict, Any, Optional, Union
from urllib.parse import urlparse

from telethon import TelegramClient
from telethon.tl import types, functions
from telethon.errors import ChannelPrivateError, UsernameNotModifiedError, FloodWaitError

from core.config.config import Config
from core.database.unified_database import DatabaseManager
from core.bot.telegram_bot import TelegramBotCore

logger = logging.getLogger(__name__)


class ChannelValidator:
    """Channel validation and processing utilities"""
    
    def __init__(self, bot, db_manager: DatabaseManager, config: Config):
        self.bot = bot
        self.db = db_manager
        self.config = config
        self.bot_core = TelegramBotCore(config, db_manager)
        
    async def validate_and_process_channel(self, user_id: int, channel_input: str) -> Dict[str, Any]:
        """Validate and process channel input"""
        try:
            # Parse channel input
            channel_info = self._parse_channel_input(channel_input)
            if not channel_info['valid']:
                return {
                    'success': False,
                    'error': channel_info['error']
                }
            
            # Get user's active accounts
            user_accounts = await self.db.get_user_accounts(user_id, active_only=True)
            if not user_accounts:
                return {
                    'success': False,
                    'error': 'No active Telegram accounts found. Please add an account first.'
                }
            
            # Try to resolve channel with user's accounts
            channel_data = None
            successful_account = None
            
            for account in user_accounts:
                try:
                    client = await self.bot_core.get_client(account['id'])
                    if not client:
                        continue
                    
                    # Check rate limits
                    if not await self.bot_core.check_rate_limit(account['id']):
                        continue
                    
                    # Try to get channel entity
                    channel_data = await self._get_channel_entity(client, channel_info)
                    if channel_data:
                        successful_account = account
                        await self.bot_core.increment_rate_limit(account['id'])
                        break
                        
                except Exception as e:
                    logger.warning(f"Failed to check channel with account {account['id']}: {e}")
                    continue
            
            if not channel_data:
                return {
                    'success': False,
                    'error': 'Could not access the channel. Please check the channel link and your permissions.'
                }
            
            # Validate user permissions
            permissions_check = await self._check_user_permissions(
                successful_account, channel_data, user_id
            )
            if not permissions_check['valid']:
                return {
                    'success': False,
                    'error': permissions_check['error']
                }
            
            # Add channel to database
            db_result = await self._add_channel_to_database(user_id, channel_data)
            if not db_result['success']:
                return db_result
            
            return {
                'success': True,
                'channel_info': channel_data,
                'permissions': permissions_check,
                'account_used': successful_account['phone_number']
            }
            
        except Exception as e:
            logger.error(f"Error validating channel: {e}")
            return {
                'success': False,
                'error': f'Validation failed: {str(e)}'
            }
    
    def _parse_channel_input(self, channel_input: str) -> Dict[str, Any]:
        """Parse different types of channel input"""
        try:
            channel_input = channel_input.strip()
            
            # Channel ID (starts with -100)
            if channel_input.startswith('-100'):
                try:
                    channel_id = int(channel_input)
                    return {
                        'valid': True,
                        'type': 'id',
                        'value': channel_id,
                        'input': channel_input
                    }
                except ValueError:
                    return {
                        'valid': False,
                        'error': 'Invalid channel ID format'
                    }
            
            # Username (starts with @)
            if channel_input.startswith('@'):
                username = channel_input[1:]
                if self._is_valid_username(username):
                    return {
                        'valid': True,
                        'type': 'username',
                        'value': username,
                        'input': channel_input
                    }
                else:
                    return {
                        'valid': False,
                        'error': 'Invalid username format'
                    }
            
            # Telegram URL
            if 'telegram.me' in channel_input or 't.me' in channel_input:
                parsed_url = urlparse(channel_input)
                path = parsed_url.path.strip('/')
                
                if path:
                    # Remove any additional parameters
                    username = path.split('/')[0]
                    if self._is_valid_username(username):
                        return {
                            'valid': True,
                            'type': 'username',
                            'value': username,
                            'input': channel_input
                        }
                
                return {
                    'valid': False,
                    'error': 'Could not extract channel information from URL'
                }
            
            # Plain username (without @)
            if self._is_valid_username(channel_input):
                return {
                    'valid': True,
                    'type': 'username',
                    'value': channel_input,
                    'input': channel_input
                }
            
            return {
                'valid': False,
                'error': 'Invalid channel format. Use @username, channel ID, or t.me link.'
            }
            
        except Exception as e:
            logger.error(f"Error parsing channel input: {e}")
            return {
                'valid': False,
                'error': 'Failed to parse channel information'
            }
    
    def _is_valid_username(self, username: str) -> bool:
        """Check if username format is valid"""
        # Username rules: 5-32 characters, alphanumeric + underscores, can't start with number
        if not username or len(username) < 5 or len(username) > 32:
            return False
        
        if username[0].isdigit():
            return False
        
        return re.match(r'^[a-zA-Z0-9_]+$', username) is not None
    
    async def _get_channel_entity(self, client: TelegramClient, channel_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get channel entity from Telegram"""
        try:
            entity = None
            
            if channel_info['type'] == 'id':
                entity = await client.get_entity(channel_info['value'])
            elif channel_info['type'] == 'username':
                entity = await client.get_entity(channel_info['value'])
            
            if not entity:
                return None
            
            # Check if it's a channel
            if not isinstance(entity, (types.Channel, types.Chat)):
                return None
            
            # Get additional channel information
            full_channel = await client(functions.channels.GetFullChannelRequest(entity))
            
            return {
                'channel_id': entity.id,
                'access_hash': getattr(entity, 'access_hash', None),
                'title': entity.title,
                'username': getattr(entity, 'username', None),
                'description': getattr(full_channel.full_chat, 'about', ''),
                'member_count': getattr(full_channel.full_chat, 'participants_count', 0),
                'is_megagroup': getattr(entity, 'megagroup', False),
                'is_broadcast': getattr(entity, 'broadcast', False),
                'is_public': bool(getattr(entity, 'username', None)),
                'created_date': getattr(entity, 'date', None)
            }
            
        except ChannelPrivateError:
            logger.warning("Channel is private or doesn't exist")
            return None
        except FloodWaitError as e:
            logger.warning(f"Rate limited, need to wait {e.seconds} seconds")
            return None
        except Exception as e:
            logger.error(f"Error getting channel entity: {e}")
            return None
    
    async def _check_user_permissions(self, account: Dict[str, Any], 
                                    channel_data: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """Check if user has necessary permissions in the channel"""
        try:
            client = await self.bot_core.get_client(account['id'])
            if not client:
                return {
                    'valid': False,
                    'error': 'Could not connect to Telegram account'
                }
            
            # Get user's participation status in the channel
            try:
                channel_entity = await client.get_entity(channel_data['channel_id'])
                participant = await client(functions.channels.GetParticipantRequest(
                    channel=channel_entity,
                    participant=await client.get_me()
                ))
                
                # Check if user is admin or has necessary permissions
                if hasattr(participant.participant, 'admin_rights'):
                    admin_rights = participant.participant.admin_rights
                    can_post = getattr(admin_rights, 'post_messages', False)
                    can_edit = getattr(admin_rights, 'edit_messages', False)
                    
                    return {
                        'valid': True,
                        'role': 'admin',
                        'permissions': {
                            'can_post': can_post,
                            'can_edit': can_edit,
                            'can_view': True
                        }
                    }
                elif hasattr(participant.participant, 'creator'):
                    return {
                        'valid': True,
                        'role': 'creator',
                        'permissions': {
                            'can_post': True,
                            'can_edit': True,
                            'can_view': True
                        }
                    }
                else:
                    # Regular member - check if channel allows this
                    return {
                        'valid': True,
                        'role': 'member',
                        'permissions': {
                            'can_post': False,
                            'can_edit': False,
                            'can_view': True
                        },
                        'warning': 'Limited permissions - some features may not work'
                    }
                    
            except Exception as e:
                # If we can't check permissions but can access the channel,
                # assume basic access is available
                logger.warning(f"Could not check detailed permissions: {e}")
                return {
                    'valid': True,
                    'role': 'unknown',
                    'permissions': {
                        'can_post': False,
                        'can_edit': False,
                        'can_view': True
                    },
                    'warning': 'Could not verify permissions'
                }
                
        except Exception as e:
            logger.error(f"Error checking permissions: {e}")
            return {
                'valid': False,
                'error': 'Failed to verify channel permissions'
            }
    
    async def _add_channel_to_database(self, user_id: int, channel_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add channel to database"""
        try:
            # Check if channel already exists
            existing_channel = await self.db.get_channel_by_channel_id(channel_data['channel_id'])
            if existing_channel:
                if existing_channel['user_id'] == user_id:
                    return {
                        'success': False,
                        'error': 'Channel is already in your list'
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Channel is already managed by another user'
                    }
            
            # Add new channel
            db_channel_id = await self.db.add_channel(
                user_id=user_id,
                channel_id=channel_data['channel_id'],
                username=channel_data.get('username'),
                title=channel_data['title'],
                description=channel_data.get('description')
            )
            
            if not db_channel_id:
                return {
                    'success': False,
                    'error': 'Failed to add channel to database'
                }
            
            # Update member count
            await self.db.update_channel_info(
                db_channel_id,
                member_count=channel_data.get('member_count', 0)
            )
            
            # Store initial analytics data
            await self.db.store_analytics_data(
                'channel', db_channel_id, 'member_count', 
                channel_data.get('member_count', 0),
                {'event': 'channel_added'}
            )
            
            return {
                'success': True,
                'db_channel_id': db_channel_id
            }
            
        except Exception as e:
            logger.error(f"Error adding channel to database: {e}")
            return {
                'success': False,
                'error': 'Database error while adding channel'
            }
    
    async def refresh_channel_info(self, channel_db_id: int) -> Dict[str, Any]:
        """Refresh channel information from Telegram"""
        try:
            # Get channel from database
            channel = await self.db.get_channel_by_id(channel_db_id)
            if not channel:
                return {
                    'success': False,
                    'error': 'Channel not found'
                }
            
            # Get user's accounts
            user_accounts = await self.db.get_user_accounts(channel['user_id'], active_only=True)
            if not user_accounts:
                return {
                    'success': False,
                    'error': 'No active accounts available'
                }
            
            # Try to refresh with available accounts
            for account in user_accounts:
                try:
                    client = await self.bot_core.get_client(account['id'])
                    if not client:
                        continue
                    
                    # Get updated channel info
                    entity = await client.get_entity(channel['channel_id'])
                    full_channel = await client(functions.channels.GetFullChannelRequest(entity))
                    
                    # Update database
                    updated = await self.db.update_channel_info(
                        channel_db_id,
                        title=entity.title,
                        description=getattr(full_channel.full_chat, 'about', ''),
                        member_count=getattr(full_channel.full_chat, 'participants_count', 0)
                    )
                    
                    if updated:
                        # Store analytics update
                        await self.db.store_analytics_data(
                            'channel', channel_db_id, 'member_count',
                            getattr(full_channel.full_chat, 'participants_count', 0),
                            {'event': 'info_refresh'}
                        )
                    
                    return {
                        'success': True,
                        'updated_info': {
                            'title': entity.title,
                            'member_count': getattr(full_channel.full_chat, 'participants_count', 0),
                            'description': getattr(full_channel.full_chat, 'about', '')
                        }
                    }
                    
                except Exception as e:
                    logger.warning(f"Failed to refresh with account {account['id']}: {e}")
                    continue
            
            return {
                'success': False,
                'error': 'Could not refresh channel information'
            }
            
        except Exception as e:
            logger.error(f"Error refreshing channel info: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def validate_channel_access(self, channel_db_id: int, account_id: int) -> bool:
        """Validate that an account can access a channel"""
        try:
            channel = await self.db.get_channel_by_id(channel_db_id)
            if not channel:
                return False
            
            client = await self.bot_core.get_client(account_id)
            if not client:
                return False
            
            # Try to get channel entity
            entity = await client.get_entity(channel['channel_id'])
            return entity is not None
            
        except Exception as e:
            logger.warning(f"Channel access validation failed: {e}")
            return False
