"""Config Flow for PlayStation 4."""
from collections import OrderedDict
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.ps4.const import (
    DEFAULT_NAME, DEFAULT_REGION, DOMAIN, REGIONS)
from homeassistant.const import (
    CONF_CODE, CONF_HOST, CONF_IP_ADDRESS, CONF_NAME, CONF_REGION, CONF_TOKEN)

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class PlayStation4FlowHandler(config_entries.ConfigFlow):
    """Handle a PlayStation 4 config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the config flow."""
        self.creds = None
        self.name = None
        self.host = None
        self.region = None
        self.pin = None

    async def async_step_user(self, user_input=None):
        """Handle a user config flow."""
        from pyps4_homeassistant import Helper
        helper = Helper()

        # Abort if device is configured.
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason='devices_configured')

        # Check if able to bind to ports: UDP 987, TCP 997.
        failed = await self.hass.async_add_executor_job(helper.port_bind)
        if failed is not None:
            reason = 'port_{}_bind_error'.format(failed)
            return self.async_abort(reason=reason)
        return await self.async_step_creds(user_input)

    async def async_step_creds(self, user_input=None):
        """Return PS4 credentials from 2nd Screen App."""
        from pyps4_homeassistant import Helper
        helper = Helper()

        if user_input is not None:
            self.creds = await self.hass.async_add_executor_job(
                helper.get_creds)

            if self.creds is not None:
                return await self.async_step_link()
            return self.async_abort(reason='credential_error')

        return self.async_show_form(
            step_id='creds')

    async def async_step_link(self, user_input=None):
        """Prompt user input. Create or edit entry."""
        from pyps4_homeassistant import Helper
        helper = Helper()

        errors = {}
        device_list = []

        # Search for device.
        devices = await self.hass.async_add_executor_job(helper.has_devices)

        # Abort if can't find device.
        if not devices:
            return self.async_abort(reason='no_devices_found')

        for device in devices:
            ip_addr = device['host-ip']
            device_list.append(ip_addr)

        # Login to PS4 with user data.
        if user_input is not None:
            self.region = user_input[CONF_REGION]
            self.name = user_input[CONF_NAME]
            self.pin = user_input[CONF_CODE]
            self.host = user_input[CONF_IP_ADDRESS]

            is_ready, is_login = await self.hass.async_add_executor_job(
                helper.link, self.host, self.creds, self.pin)

            if is_ready is False:
                errors['base'] = 'not_ready'
            elif is_login is False:
                errors['base'] = 'login_failed'
            else:
                device = {
                    CONF_HOST: self.host,
                    CONF_NAME: self.name,
                    CONF_REGION: self.region
                }

                # Create entry.
                return self.async_create_entry(
                    title='PlayStation 4',
                    data={
                        CONF_TOKEN: self.creds,
                        'devices': [device],
                    },
                )

        # Show User Input form.
        link_schema = OrderedDict()
        link_schema[vol.Required(CONF_IP_ADDRESS)] = vol.In(list(device_list))
        link_schema[vol.Required(
            CONF_REGION, default=DEFAULT_REGION)] = vol.In(list(REGIONS))
        link_schema[vol.Required(CONF_CODE)] = str
        link_schema[vol.Required(CONF_NAME, default=DEFAULT_NAME)] = str

        return self.async_show_form(
            step_id='link',
            data_schema=vol.Schema(link_schema),
            errors=errors,
        )
