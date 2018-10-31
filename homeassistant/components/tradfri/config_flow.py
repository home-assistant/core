"""Config flow for Tradfri."""
import asyncio
from collections import OrderedDict
from uuid import uuid4

import async_timeout
import voluptuous as vol

from homeassistant import config_entries

from .const import (
    CONF_IMPORT_GROUPS, CONF_IDENTITY, CONF_HOST, CONF_KEY, CONF_GATEWAY_ID)

KEY_HOST = 'host'
KEY_SECURITY_CODE = 'security_code'
KEY_IMPORT_GROUPS = 'import_groups'


class AuthError(Exception):
    """Exception if authentication occurs."""

    def __init__(self, code):
        """Initialize exception."""
        super().__init__()
        self.code = code


@config_entries.HANDLERS.register('tradfri')
class FlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize flow."""
        self._host = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_auth()

    async def async_step_auth(self, user_input=None):
        """Handle the authentication with a gateway."""
        errors = {}

        if user_input is not None:
            host = user_input.get(KEY_HOST, self._host)
            try:
                auth = await authenticate(
                    self.hass, host,
                    user_input[KEY_SECURITY_CODE])

                # We don't ask for import group anymore as group state
                # is not reliable, don't want to show that to the user.
                auth[CONF_IMPORT_GROUPS] = False

                return await self._entry_from_data(auth)

            except AuthError as err:
                if err.code == 'invalid_security_code':
                    errors[KEY_SECURITY_CODE] = err.code
                else:
                    errors['base'] = err.code

        fields = OrderedDict()

        if self._host is None:
            fields[vol.Required(KEY_HOST)] = str

        fields[vol.Required(KEY_SECURITY_CODE)] = str

        return self.async_show_form(
            step_id='auth',
            data_schema=vol.Schema(fields),
            errors=errors,
        )

    async def async_step_discovery(self, user_input):
        """Handle discovery."""
        self._host = user_input['host']
        return await self.async_step_auth()

    async def async_step_import(self, user_input):
        """Import a config entry."""
        for entry in self._async_current_entries():
            if entry.data[CONF_HOST] == user_input['host']:
                return self.async_abort(
                    reason='already_configured'
                )

        # Happens if user has host directly in configuration.yaml
        if 'key' not in user_input:
            self._host = user_input['host']
            return await self.async_step_auth()

        try:
            data = await get_gateway_info(
                self.hass, user_input['host'],
                # Old config format had a fixed identity
                user_input.get('identity', 'homeassistant'),
                user_input['key'])

            data[CONF_IMPORT_GROUPS] = user_input[CONF_IMPORT_GROUPS]

            return await self._entry_from_data(data)
        except AuthError:
            # If we fail to connect, just pass it on to discovery
            self._host = user_input['host']
            return await self.async_step_auth()

    async def _entry_from_data(self, data):
        """Create an entry from data."""
        host = data[CONF_HOST]
        gateway_id = data[CONF_GATEWAY_ID]

        same_hub_entries = [entry.entry_id for entry
                            in self._async_current_entries()
                            if entry.data[CONF_GATEWAY_ID] == gateway_id or
                            entry.data[CONF_HOST] == host]

        if same_hub_entries:
            await asyncio.wait([self.hass.config_entries.async_remove(entry_id)
                                for entry_id in same_hub_entries])

        return self.async_create_entry(
            title=host,
            data=data
        )


async def authenticate(hass, host, security_code):
    """Authenticate with a Tradfri hub."""
    from pytradfri.api.aiocoap_api import APIFactory
    from pytradfri import RequestError

    identity = uuid4().hex

    api_factory = APIFactory(host, psk_id=identity, loop=hass.loop)

    try:
        with async_timeout.timeout(5):
            key = await api_factory.generate_psk(security_code)
    except RequestError:
        raise AuthError('invalid_security_code')
    except asyncio.TimeoutError:
        raise AuthError('timeout')

    return await get_gateway_info(hass, host, identity, key)


async def get_gateway_info(hass, host, identity, key):
    """Return info for the gateway."""
    from pytradfri.api.aiocoap_api import APIFactory
    from pytradfri import Gateway, RequestError

    try:
        factory = APIFactory(
            host,
            psk_id=identity,
            psk=key,
            loop=hass.loop
        )
        api = factory.request
        gateway = Gateway()
        gateway_info_result = await api(gateway.get_gateway_info())
    except RequestError:
        raise AuthError('cannot_connect')

    return {
        CONF_HOST: host,
        CONF_IDENTITY: identity,
        CONF_KEY: key,
        CONF_GATEWAY_ID: gateway_info_result.id,
    }
