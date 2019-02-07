"""Config flow to configure esphome component."""
from collections import OrderedDict
from typing import Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import ConfigType


@config_entries.HANDLERS.register('esphome')
class EsphomeFlowHandler(config_entries.ConfigFlow):
    """Handle a esphome config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize flow."""
        self._host = None  # type: Optional[str]
        self._port = None  # type: Optional[int]
        self._password = None  # type: Optional[str]
        self._name = None  # type: Optional[str]

    async def async_step_user(self, user_input: Optional[ConfigType] = None,
                              error: Optional[str] = None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self._host = user_input['host']
            self._port = user_input['port']
            error, device_info = await self.fetch_device_info()
            if error is not None:
                return await self.async_step_user(error=error)
            self._name = device_info.name

            # Only show authentication step if device uses password
            if device_info.uses_password:
                return await self.async_step_authenticate()

            return self._async_get_entry()

        fields = OrderedDict()
        fields[vol.Required('host', default=self._host or vol.UNDEFINED)] = str
        fields[vol.Optional('port', default=self._port or 6053)] = int

        errors = {}
        if error is not None:
            errors['base'] = error

        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema(fields),
            errors=errors
        )

    async def async_step_discovery(self, user_input: ConfigType):
        """Handle discovery."""
        # mDNS hostname has additional '.' at end
        hostname = user_input['hostname'][:-1]
        hosts = (hostname, user_input['host'])
        for entry in self._async_current_entries():
            if entry.data['host'] in hosts:
                return self.async_abort(
                    reason='already_configured'
                )

        # Prefer .local addresses (mDNS is available after all, otherwise
        # we wouldn't have received the discovery message)
        return await self.async_step_user(user_input={
            'host': hostname,
            'port': user_input['port'],
        })

    def _async_get_entry(self):
        return self.async_create_entry(
            title=self._name,
            data={
                'host': self._host,
                'port': self._port,
                # The API uses protobuf, so empty string denotes absence
                'password': self._password or '',
            }
        )

    async def async_step_authenticate(self, user_input=None, error=None):
        """Handle getting password for authentication."""
        if user_input is not None:
            self._password = user_input['password']
            error = await self.try_login()
            if error:
                return await self.async_step_authenticate(error=error)
            return self._async_get_entry()

        errors = {}
        if error is not None:
            errors['base'] = error

        return self.async_show_form(
            step_id='authenticate',
            data_schema=vol.Schema({
                vol.Required('password'): str
            }),
            errors=errors
        )

    async def fetch_device_info(self):
        """Fetch device info from API and return any errors."""
        from aioesphomeapi import APIClient, APIConnectionError

        cli = APIClient(self.hass.loop, self._host, self._port, '')

        try:
            await cli.connect()
            device_info = await cli.device_info()
        except APIConnectionError as err:
            if 'resolving' in str(err):
                return 'resolve_error', None
            return 'connection_error', None
        finally:
            await cli.disconnect(force=True)

        return None, device_info

    async def try_login(self):
        """Try logging in to device and return any errors."""
        from aioesphomeapi import APIClient, APIConnectionError

        cli = APIClient(self.hass.loop, self._host, self._port, self._password)

        try:
            await cli.connect(login=True)
        except APIConnectionError:
            await cli.disconnect(force=True)
            return 'invalid_password'

        return None
