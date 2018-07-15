"""Storage for auth models."""
from collections import OrderedDict
from datetime import timedelta

from homeassistant.util import dt as dt_util

from . import models

STORAGE_VERSION = 1
STORAGE_KEY = 'auth'


class AuthStore:
    """Stores authentication info.

    Any mutation to an object should happen inside the auth store.

    The auth store is lazy. It won't load the data from disk until a method is
    called that needs it.
    """

    def __init__(self, hass):
        """Initialize the auth store."""
        self.hass = hass
        self._users = None
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)

    async def async_get_users(self):
        """Retrieve all users."""
        if self._users is None:
            await self.async_load()

        return list(self._users.values())

    async def async_get_user(self, user_id):
        """Retrieve a user by id."""
        if self._users is None:
            await self.async_load()

        return self._users.get(user_id)

    async def async_create_user(self, name, is_owner=None, is_active=None,
                                system_generated=None, credentials=None):
        """Create a new user."""
        if self._users is None:
            await self.async_load()

        kwargs = {
            'name': name
        }

        if is_owner is not None:
            kwargs['is_owner'] = is_owner

        if is_active is not None:
            kwargs['is_active'] = is_active

        if system_generated is not None:
            kwargs['system_generated'] = system_generated

        new_user = models.User(**kwargs)

        self._users[new_user.id] = new_user

        if credentials is None:
            await self.async_save()
            return new_user

        # Saving is done inside the link.
        await self.async_link_user(new_user, credentials)
        return new_user

    async def async_link_user(self, user, credentials):
        """Add credentials to an existing user."""
        user.credentials.append(credentials)
        await self.async_save()
        credentials.is_new = False

    async def async_remove_user(self, user):
        """Remove a user."""
        self._users.pop(user.id)
        await self.async_save()

    async def async_activate_user(self, user):
        """Activate a user."""
        user.is_active = True
        await self.async_save()

    async def async_deactivate_user(self, user):
        """Activate a user."""
        user.is_active = False
        await self.async_save()

    async def async_remove_credentials(self, credentials):
        """Remove credentials."""
        for user in self._users.values():
            found = None

            for index, cred in enumerate(user.credentials):
                if cred is credentials:
                    found = index
                    break

            if found is not None:
                user.credentials.pop(found)
                break

        await self.async_save()

    async def async_create_refresh_token(self, user, client_id=None):
        """Create a new token for a user."""
        refresh_token = models.RefreshToken(user=user, client_id=client_id)
        user.refresh_tokens[refresh_token.token] = refresh_token
        await self.async_save()
        return refresh_token

    async def async_get_refresh_token(self, token):
        """Get refresh token by token."""
        if self._users is None:
            await self.async_load()

        for user in self._users.values():
            refresh_token = user.refresh_tokens.get(token)
            if refresh_token is not None:
                return refresh_token

        return None

    async def async_load(self):
        """Load the users."""
        data = await self._store.async_load()

        # Make sure that we're not overriding data if 2 loads happened at the
        # same time
        if self._users is not None:
            return

        users = OrderedDict()

        if data is None:
            self._users = users
            return

        for user_dict in data['users']:
            users[user_dict['id']] = models.User(**user_dict)

        for cred_dict in data['credentials']:
            users[cred_dict['user_id']].credentials.append(models.Credentials(
                id=cred_dict['id'],
                is_new=False,
                auth_provider_type=cred_dict['auth_provider_type'],
                auth_provider_id=cred_dict['auth_provider_id'],
                data=cred_dict['data'],
            ))

        refresh_tokens = OrderedDict()

        for rt_dict in data['refresh_tokens']:
            token = models.RefreshToken(
                id=rt_dict['id'],
                user=users[rt_dict['user_id']],
                client_id=rt_dict['client_id'],
                created_at=dt_util.parse_datetime(rt_dict['created_at']),
                access_token_expiration=timedelta(
                    seconds=rt_dict['access_token_expiration']),
                token=rt_dict['token'],
            )
            refresh_tokens[token.id] = token
            users[rt_dict['user_id']].refresh_tokens[token.token] = token

        for ac_dict in data['access_tokens']:
            refresh_token = refresh_tokens[ac_dict['refresh_token_id']]
            token = models.AccessToken(
                refresh_token=refresh_token,
                created_at=dt_util.parse_datetime(ac_dict['created_at']),
                token=ac_dict['token'],
            )
            refresh_token.access_tokens.append(token)

        self._users = users

    async def async_save(self):
        """Save users."""
        users = [
            {
                'id': user.id,
                'is_owner': user.is_owner,
                'is_active': user.is_active,
                'name': user.name,
                'system_generated': user.system_generated,
            }
            for user in self._users.values()
        ]

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
                'created_at': refresh_token.created_at.isoformat(),
                'access_token_expiration':
                    refresh_token.access_token_expiration.total_seconds(),
                'token': refresh_token.token,
            }
            for user in self._users.values()
            for refresh_token in user.refresh_tokens.values()
        ]

        access_tokens = [
            {
                'id': user.id,
                'refresh_token_id': refresh_token.id,
                'created_at': access_token.created_at.isoformat(),
                'token': access_token.token,
            }
            for user in self._users.values()
            for refresh_token in user.refresh_tokens.values()
            for access_token in refresh_token.access_tokens
        ]

        data = {
            'users': users,
            'credentials': credentials,
            'access_tokens': access_tokens,
            'refresh_tokens': refresh_tokens,
        }

        await self._store.async_save(data, delay=1)
