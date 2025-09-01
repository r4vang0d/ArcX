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
            validation_errors = []
            
            for account in user_accounts:
                try:
                    client = await self.bot_core.get_client(account['id'])
                    if not client:
                        validation_errors.append(f"Account {account.get('phone_number', account['id'])}: Not connected")
                        continue
                    
                    # Check rate limits
                    if not await self.bot_core.check_rate_limit(account['id']):
                        validation_errors.append(f"Account {account.get('phone_number', account['id'])}: Rate limited")
                        continue
                    
                    # Try to get channel entity
                    result = await self._get_channel_entity_with_details(client, channel_info, account)
                    if result['success']:
                        channel_data = result['data']
                        successful_account = account
                        await self.bot_core.increment_rate_limit(account['id'])
                        break
                    else:
                        validation_errors.append(f"Account {account.get('phone_number', account['id'])}: {result['error']}")
                        
                except Exception as e:
                    error_msg = f"Account {account.get('phone_number', account['id'])}: {str(e)}"
                    validation_errors.append(error_msg)
                    logger.warning(f"Failed to check channel with account {account['id']}: {e}")
                    continue
            
            if not channel_data:
                # Provide detailed error information
                error_details = "\n".join(validation_errors) if validation_errors else "No accounts could access the channel"
                
                # Check if channel exists at all
                channel_status = await self._check_channel_existence(channel_info)
                
                return {
                    'success': False,
                    'error': f"Could not access channel '{channel_input}'.\n\n🔍 **Validation Details:**\n{error_details}\n\n{channel_status['message']}"
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
            
            # Telegram URLs - Enhanced parsing for all link types
            if any(domain in channel_input.lower() for domain in ['telegram.me', 't.me', 'telegram.org']):
                return self._parse_telegram_url(channel_input)
            
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
                'error': 'Invalid channel format. Supported formats:\n• @username\n• https://t.me/username\n• https://t.me/joinchat/xxxxx\n• https://t.me/+xxxxx\n• Channel ID (-100xxxxxxxxx)'
            }
            
        except Exception as e:
            logger.error(f"Error parsing channel input: {e}")
            return {
                'valid': False,
                'error': 'Failed to parse channel information'
            }
    
    def _parse_telegram_url(self, url: str) -> Dict[str, Any]:
        """Parse various Telegram URL formats"""
        try:
            # Clean and normalize URL
            url = url.strip()
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            parsed_url = urlparse(url)
            path = parsed_url.path.strip('/')
            
            # Handle different URL patterns
            if 'joinchat' in path:
                # Private group/channel invite link: t.me/joinchat/xxxxx
                invite_hash = path.split('joinchat/')[-1]
                if invite_hash and len(invite_hash) > 10:  # Reasonable hash length
                    return {
                        'valid': True,
                        'type': 'invite_link',
                        'value': invite_hash,
                        'input': url,
                        'full_path': path
                    }
                else:
                    return {
                        'valid': False,
                        'error': 'Invalid invite link format'
                    }
            
            elif path.startswith('+'):
                # New style private invite: t.me/+xxxxx
                invite_hash = path[1:]  # Remove the + sign
                if invite_hash and len(invite_hash) > 10:
                    return {
                        'valid': True,
                        'type': 'invite_link',
                        'value': invite_hash,
                        'input': url,
                        'full_path': path
                    }
                else:
                    return {
                        'valid': False,
                        'error': 'Invalid private invite link format'
                    }
            
            elif '/c/' in path:
                # Channel with ID: t.me/c/channel_id/message_id
                parts = path.split('/c/')
                if len(parts) > 1:
                    channel_part = parts[1].split('/')[0]
                    try:
                        channel_id = int(channel_part)
                        # Convert to full channel ID format
                        full_channel_id = -1000000000000 - channel_id
                        return {
                            'valid': True,
                            'type': 'id',
                            'value': full_channel_id,
                            'input': url
                        }
                    except ValueError:
                        return {
                            'valid': False,
                            'error': 'Invalid channel ID in URL'
                        }
            
            elif path and not any(x in path for x in ['/', '?', '#']):
                # Simple username: t.me/username
                username = path
                if self._is_valid_username(username):
                    return {
                        'valid': True,
                        'type': 'username',
                        'value': username,
                        'input': url
                    }
                else:
                    return {
                        'valid': False,
                        'error': 'Invalid username in URL'
                    }
            
            elif '/' in path:
                # Username with possible message ID: t.me/username/123
                username = path.split('/')[0]
                if username and self._is_valid_username(username):
                    return {
                        'valid': True,
                        'type': 'username',
                        'value': username,
                        'input': url
                    }
                else:
                    return {
                        'valid': False,
                        'error': 'Invalid username in URL'
                    }
            
            return {
                'valid': False,
                'error': 'Could not parse Telegram URL format'
            }
            
        except Exception as e:
            logger.error(f"Error parsing Telegram URL: {e}")
            return {
                'valid': False,
                'error': 'Failed to parse URL'
            }

    def _is_valid_username(self, username: str) -> bool:
        """Check if username format is valid"""
        # Username rules: 4-32 characters, alphanumeric + underscores, can't start with number
        # Made more lenient to handle more valid usernames
        if not username or len(username) < 4 or len(username) > 32:
            return False
        
        if username[0].isdigit():
            return False
        
        # Allow letters, numbers, and underscores
        return re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', username) is not None
    
    async def _get_channel_entity_with_details(self, client: TelegramClient, channel_info: Dict[str, Any], account: Dict[str, Any]) -> Dict[str, Any]:
        """Get channel entity with detailed error reporting"""
        try:
            entity = None
            
            if channel_info['type'] == 'id':
                entity = await client.get_entity(channel_info['value'])
            elif channel_info['type'] == 'username':
                # Try both with and without @ symbol
                username = channel_info['value']
                try:
                    entity = await client.get_entity(username)
                except Exception:
                    # Try with @ prefix if not already there
                    if not username.startswith('@'):
                        entity = await client.get_entity('@' + username)
                    else:
                        raise
            elif channel_info['type'] == 'invite_link':
                entity = await self._resolve_invite_link(client, channel_info['value'])
            
            if not entity:
                return {
                    'success': False,
                    'error': 'Channel not found or invalid'
                }
            
            # Check if it's a channel or group
            if not isinstance(entity, (types.Channel, types.Chat)):
                return {
                    'success': False,
                    'error': f'This is a {type(entity).__name__}, not a channel or group'
                }
            
            # Get additional channel information
            try:
                if isinstance(entity, types.Channel):
                    full_channel = await client(functions.channels.GetFullChannelRequest(entity))
                    full_chat = full_channel.full_chat
                else:
                    # For regular chats
                    full_chat_request = functions.messages.GetFullChatRequest(entity.id)
                    full_chat_result = await client(full_chat_request)
                    full_chat = full_chat_result.full_chat
            except Exception as e:
                logger.warning(f"Could not get full channel info: {e}")
                full_chat = None
            
            channel_data = {
                'channel_id': entity.id,
                'access_hash': getattr(entity, 'access_hash', None),
                'title': entity.title,
                'username': getattr(entity, 'username', None),
                'description': getattr(full_chat, 'about', '') if full_chat else '',
                'member_count': getattr(full_chat, 'participants_count', 0) if full_chat else 0,
                'is_megagroup': getattr(entity, 'megagroup', False),
                'is_broadcast': getattr(entity, 'broadcast', False),
                'is_public': bool(getattr(entity, 'username', None)),
                'created_date': getattr(entity, 'date', None),
                'is_private': channel_info['type'] == 'invite_link'
            }
            
            return {
                'success': True,
                'data': channel_data
            }
            
        except ChannelPrivateError:
            return {
                'success': False,
                'error': 'Channel is private and you are not a member'
            }
        except FloodWaitError as e:
            return {
                'success': False,
                'error': f'Rate limited, wait {e.seconds} seconds'
            }
        except ValueError as e:
            if 'username' in str(e).lower():
                return {
                    'success': False,
                    'error': 'Username not found or invalid'
                }
            return {
                'success': False,
                'error': f'Invalid format: {str(e)}'
            }
        except Exception as e:
            error_type = type(e).__name__
            return {
                'success': False,
                'error': f'{error_type}: {str(e)}'
            }
    
    async def _get_channel_entity(self, client: TelegramClient, channel_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get channel entity from Telegram"""
        try:
            entity = None
            
            if channel_info['type'] == 'id':
                entity = await client.get_entity(channel_info['value'])
            elif channel_info['type'] == 'username':
                entity = await client.get_entity(channel_info['value'])
            elif channel_info['type'] == 'invite_link':
                # Handle invite links
                entity = await self._resolve_invite_link(client, channel_info['value'])
            
            if not entity:
                return None
            
            # Check if it's a channel or group
            if not isinstance(entity, (types.Channel, types.Chat)):
                return None
            
            # Get additional channel information
            try:
                if isinstance(entity, types.Channel):
                    full_channel = await client(functions.channels.GetFullChannelRequest(entity))
                    full_chat = full_channel.full_chat
                else:
                    # For regular chats
                    full_chat_request = functions.messages.GetFullChatRequest(entity.id)
                    full_chat_result = await client(full_chat_request)
                    full_chat = full_chat_result.full_chat
            except Exception as e:
                logger.warning(f"Could not get full channel info: {e}")
                # Fallback to basic info
                full_chat = None
            
            return {
                'channel_id': entity.id,
                'access_hash': getattr(entity, 'access_hash', None),
                'title': entity.title,
                'username': getattr(entity, 'username', None),
                'description': getattr(full_chat, 'about', '') if full_chat else '',
                'member_count': getattr(full_chat, 'participants_count', 0) if full_chat else 0,
                'is_megagroup': getattr(entity, 'megagroup', False),
                'is_broadcast': getattr(entity, 'broadcast', False),
                'is_public': bool(getattr(entity, 'username', None)),
                'created_date': getattr(entity, 'date', None),
                'is_private': channel_info['type'] == 'invite_link'
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
    
    async def _check_channel_existence(self, channel_info: Dict[str, Any]) -> Dict[str, Any]:
        """Check if channel exists using public methods"""
        try:
            if channel_info['type'] == 'username':
                username = channel_info['value']
                return {
                    'exists': 'unknown',
                    'message': f"💡 **Troubleshooting Tips:**\n• Make sure '@{username}' is spelled correctly\n• Check if the channel is public (has a username)\n• Verify your accounts are active and connected\n• Try adding the channel using its invite link instead"
                }
            elif channel_info['type'] == 'invite_link':
                return {
                    'exists': 'unknown', 
                    'message': f"💡 **For Private Channels:**\n• Make sure the invite link is valid and not expired\n• Your account needs to join the channel first\n• Some private channels restrict access"
                }
            else:
                return {
                    'exists': 'unknown',
                    'message': f"💡 **Channel ID Issues:**\n• Verify the channel ID format is correct\n• Channel might be deleted or restricted\n• Your accounts may not have access"
                }
        except Exception as e:
            return {
                'exists': 'unknown',
                'message': f"💡 **General Tips:**\n• Try refreshing your account connections\n• Make sure the channel exists and is accessible\n• Contact channel admin if it's a private channel"
            }

    async def _resolve_invite_link(self, client: TelegramClient, invite_hash: str) -> Optional[types.Channel]:
        """Resolve invite link to get channel entity"""
        try:
            # First, try to check the invite without joining
            invite_info = await client(functions.messages.CheckChatInviteRequest(invite_hash))
            
            if hasattr(invite_info, 'chat'):
                # We can see the chat info without joining
                return invite_info.chat
            elif hasattr(invite_info, 'channel'):
                # We can see the channel info without joining
                return invite_info.channel
            else:
                # We need to join to access the channel
                logger.info("Attempting to join channel via invite link...")
                result = await client(functions.messages.ImportChatInviteRequest(invite_hash))
                
                if hasattr(result, 'chats') and result.chats:
                    return result.chats[0]
                elif hasattr(result, 'chat'):
                    return result.chat
                
            return None
            
        except Exception as e:
            logger.error(f"Error resolving invite link: {e}")
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
