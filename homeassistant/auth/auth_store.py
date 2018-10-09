"""Storage for auth models."""
from collections import OrderedDict
from datetime import timedelta
import hmac
from logging import getLogger
from typing import Any, Dict, List, Optional  # noqa: F401

from homeassistant.auth.const import ACCESS_TOKEN_EXPIRATION
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from . import models
from .permissions import DEFAULT_POLICY

STORAGE_VERSION = 1
STORAGE_KEY = 'auth'
INITIAL_GROUP_NAME = 'All Access'


class AuthStore:
    """Stores authentication info.

    Any mutation to an object should happen inside the auth store.

    The auth store is lazy. It won't load the data from disk until a method is
    called that needs it.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the auth store."""
        self.hass = hass
        self._users = None  # type: Optional[Dict[str, models.User]]
        self._groups = None  # type: Optional[Dict[str, models.Group]]
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY,
                                                 private=True)

    async def async_get_groups(self) -> List[models.Group]:
        """Retrieve all users."""
        if self._groups is None:
            await self._async_load()
            assert self._groups is not None

        return list(self._groups.values())

    async def async_get_users(self) -> List[models.User]:
        """Retrieve all users."""
        if self._users is None:
            await self._async_load()
            assert self._users is not None

        return list(self._users.values())

    async def async_get_user(self, user_id: str) -> Optional[models.User]:
        """Retrieve a user by id."""
        if self._users is None:
            await self._async_load()
            assert self._users is not None

        return self._users.get(user_id)

    async def async_create_user(
            self, name: Optional[str], is_owner: Optional[bool] = None,
            is_active: Optional[bool] = None,
            system_generated: Optional[bool] = None,
            credentials: Optional[models.Credentials] = None,
            groups: Optional[List[models.Group]] = None) -> models.User:
        """Create a new user."""
        if self._users is None:
            await self._async_load()

        assert self._users is not None
        assert self._groups is not None

        kwargs = {
            'name': name,
            # Until we get group management, we just put everyone in the
            # same group.
            'groups': groups or [],
        }  # type: Dict[str, Any]

        if is_owner is not None:
            kwargs['is_owner'] = is_owner

        if is_active is not None:
            kwargs['is_active'] = is_active

        if system_generated is not None:
            kwargs['system_generated'] = system_generated

        new_user = models.User(**kwargs)

        self._users[new_user.id] = new_user

        if credentials is None:
            self._async_schedule_save()
            return new_user

        # Saving is done inside the link.
        await self.async_link_user(new_user, credentials)
        return new_user

    async def async_link_user(self, user: models.User,
                              credentials: models.Credentials) -> None:
        """Add credentials to an existing user."""
        user.credentials.append(credentials)
        self._async_schedule_save()
        credentials.is_new = False

    async def async_remove_user(self, user: models.User) -> None:
        """Remove a user."""
        if self._users is None:
            await self._async_load()
            assert self._users is not None

        self._users.pop(user.id)
        self._async_schedule_save()

    async def async_activate_user(self, user: models.User) -> None:
        """Activate a user."""
        user.is_active = True
        self._async_schedule_save()

    async def async_deactivate_user(self, user: models.User) -> None:
        """Activate a user."""
        user.is_active = False
        self._async_schedule_save()

    async def async_remove_credentials(
            self, credentials: models.Credentials) -> None:
        """Remove credentials."""
        if self._users is None:
            await self._async_load()
            assert self._users is not None

        for user in self._users.values():
            found = None

            for index, cred in enumerate(user.credentials):
                if cred is credentials:
                    found = index
                    break

            if found is not None:
                user.credentials.pop(found)
                break

        self._async_schedule_save()

    async def async_create_refresh_token(
            self, user: models.User, client_id: Optional[str] = None,
            client_name: Optional[str] = None,
            client_icon: Optional[str] = None,
            token_type: str = models.TOKEN_TYPE_NORMAL,
            access_token_expiration: timedelta = ACCESS_TOKEN_EXPIRATION) \
            -> models.RefreshToken:
        """Create a new token for a user."""
        kwargs = {
            'user': user,
            'client_id': client_id,
            'token_type': token_type,
            'access_token_expiration': access_token_expiration
        }  # type: Dict[str, Any]
        if client_name:
            kwargs['client_name'] = client_name
        if client_icon:
            kwargs['client_icon'] = client_icon

        refresh_token = models.RefreshToken(**kwargs)
        user.refresh_tokens[refresh_token.id] = refresh_token

        self._async_schedule_save()
        return refresh_token

    async def async_remove_refresh_token(
            self, refresh_token: models.RefreshToken) -> None:
        """Remove a refresh token."""
        if self._users is None:
            await self._async_load()
            assert self._users is not None

        for user in self._users.values():
            if user.refresh_tokens.pop(refresh_token.id, None):
                self._async_schedule_save()
                break

    async def async_get_refresh_token(
            self, token_id: str) -> Optional[models.RefreshToken]:
        """Get refresh token by id."""
        if self._users is None:
            await self._async_load()
            assert self._users is not None

        for user in self._users.values():
            refresh_token = user.refresh_tokens.get(token_id)
            if refresh_token is not None:
                return refresh_token

        return None

    async def async_get_refresh_token_by_token(
            self, token: str) -> Optional[models.RefreshToken]:
        """Get refresh token by token."""
        if self._users is None:
            await self._async_load()
            assert self._users is not None

        found = None

        for user in self._users.values():
            for refresh_token in user.refresh_tokens.values():
                if hmac.compare_digest(refresh_token.token, token):
                    found = refresh_token

        return found

    @callback
    def async_log_refresh_token_usage(
            self, refresh_token: models.RefreshToken,
            remote_ip: Optional[str] = None) -> None:
        """Update refresh token last used information."""
        refresh_token.last_used_at = dt_util.utcnow()
        refresh_token.last_used_ip = remote_ip
        self._async_schedule_save()

    async def _async_load(self) -> None:
        """Load the users."""
        data = await self._store.async_load()

        # Make sure that we're not overriding data if 2 loads happened at the
        # same time
        if self._users is not None:
            return

        if data is None:
            self._set_defaults()
            return

        users = OrderedDict()  # type: Dict[str, models.User]
        groups = OrderedDict()  # type: Dict[str, models.Group]

        # When creating objects we mention each attribute explicetely. This
        # prevents crashing if user rolls back HA version after a new property
        # was added.

        for group_dict in data.get('groups', []):
            groups[group_dict['id']] = models.Group(
                name=group_dict['name'],
                id=group_dict['id'],
                policy=group_dict.get('policy', DEFAULT_POLICY),
            )

        migrate_group = None

        if not groups:
            migrate_group = models.Group(
                name=INITIAL_GROUP_NAME,
                policy=DEFAULT_POLICY
            )
            groups[migrate_group.id] = migrate_group

        for user_dict in data['users']:
            users[user_dict['id']] = models.User(
                name=user_dict['name'],
                groups=[groups[group_id] for group_id
                        in user_dict.get('group_ids', [])],
                id=user_dict['id'],
                is_owner=user_dict['is_owner'],
                is_active=user_dict['is_active'],
                system_generated=user_dict['system_generated'],
            )
            if migrate_group is not None and not user_dict['system_generated']:
                users[user_dict['id']].groups = [migrate_group]

        for cred_dict in data['credentials']:
            users[cred_dict['user_id']].credentials.append(models.Credentials(
                id=cred_dict['id'],
                is_new=False,
                auth_provider_type=cred_dict['auth_provider_type'],
                auth_provider_id=cred_dict['auth_provider_id'],
                data=cred_dict['data'],
            ))

        for rt_dict in data['refresh_tokens']:
            # Filter out the old keys that don't have jwt_key (pre-0.76)
            if 'jwt_key' not in rt_dict:
                continue

            created_at = dt_util.parse_datetime(rt_dict['created_at'])
            if created_at is None:
                getLogger(__name__).error(
                    'Ignoring refresh token %(id)s with invalid created_at '
                    '%(created_at)s for user_id %(user_id)s', rt_dict)
                continue

            token_type = rt_dict.get('token_type')
            if token_type is None:
                if rt_dict['client_id'] is None:
                    token_type = models.TOKEN_TYPE_SYSTEM
                else:
                    token_type = models.TOKEN_TYPE_NORMAL

            # old refresh_token don't have last_used_at (pre-0.78)
            last_used_at_str = rt_dict.get('last_used_at')
            if last_used_at_str:
                last_used_at = dt_util.parse_datetime(last_used_at_str)
            else:
                last_used_at = None

            token = models.RefreshToken(
                id=rt_dict['id'],
                user=users[rt_dict['user_id']],
                client_id=rt_dict['client_id'],
                # use dict.get to keep backward compatibility
                client_name=rt_dict.get('client_name'),
                client_icon=rt_dict.get('client_icon'),
                token_type=token_type,
                created_at=created_at,
                access_token_expiration=timedelta(
                    seconds=rt_dict['access_token_expiration']),
                token=rt_dict['token'],
                jwt_key=rt_dict['jwt_key'],
                last_used_at=last_used_at,
                last_used_ip=rt_dict.get('last_used_ip'),
            )
            users[rt_dict['user_id']].refresh_tokens[token.id] = token

        self._groups = groups
        self._users = users

    @callback
    def _async_schedule_save(self) -> None:
        """Save users."""
        if self._users is None:
            return

        self._store.async_delay_save(self._data_to_save, 1)

    @callback
    def _data_to_save(self) -> Dict:
        """Return the data to store."""
        assert self._users is not None
        assert self._groups is not None

        users = [
            {
                'id': user.id,
                'group_ids': [group.id for group in user.groups],
                'is_owner': user.is_owner,
                'is_active': user.is_active,
                'name': user.name,
                'system_generated': user.system_generated,
            }
            for user in self._users.values()
        ]

        groups = []
        for group in self._groups.values():
            g_dict = {
                'name': group.name,
                'id': group.id,
            }  # type: Dict[str, Any]

            if group.policy is not DEFAULT_POLICY:
                g_dict['policy'] = group.policy

            groups.append(g_dict)

        credentials = [
            {
                'id': credential.id,
                'user_id': user.id,
                'auth_provider_type': credential.auth_provider_type,
                'auth_provider_id': credential.auth_provider_id,
                'data': credential.data,
            }
            for user in self._users.values()
            for credential in user.credentials
        ]

        refresh_tokens = [
            {
                'id': refresh_token.id,
                'user_id': user.id,
                'client_id': refresh_token.client_id,
                'client_name': refresh_token.client_name,
                'client_icon': refresh_token.client_icon,
                'token_type': refresh_token.token_type,
                'created_at': refresh_token.created_at.isoformat(),
                'access_token_expiration':
                    refresh_token.access_token_expiration.total_seconds(),
                'token': refresh_token.token,
                'jwt_key': refresh_token.jwt_key,
                'last_used_at':
                    refresh_token.last_used_at.isoformat()
                    if refresh_token.last_used_at else None,
                'last_used_ip': refresh_token.last_used_ip,
            }
            for user in self._users.values()
            for refresh_token in user.refresh_tokens.values()
        ]

        return {
            'users': users,
            'groups': groups,
            'credentials': credentials,
            'refresh_tokens': refresh_tokens,
        }

    def _set_defaults(self) -> None:
        """Set default values for auth store."""
        self._users = OrderedDict()  # type: Dict[str, models.User]

        # Add default group
        all_access_group = models.Group(
            name=INITIAL_GROUP_NAME,
            policy=DEFAULT_POLICY,
        )

        groups = OrderedDict()  # type: Dict[str, models.Group]
        groups[all_access_group.id] = all_access_group

        self._groups = groups
