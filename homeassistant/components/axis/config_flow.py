"""Config flow to configure Axis devices."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_DEVICE, CONF_HOST, CONF_MAC, CONF_NAME, CONF_PASSWORD, CONF_PORT,
    CONF_USERNAME)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.util.json import load_json

from .const import CONF_MODEL, DOMAIN
from .device import get_device
from .errors import AlreadyConfigured, AuthenticationRequired, CannotConnect

CONFIG_FILE = 'axis.conf'

EVENT_TYPES = ['motion', 'vmd3', 'pir', 'sound',
               'daynight', 'tampering', 'input']

PLATFORMS = ['camera']

AXIS_INCLUDE = EVENT_TYPES + PLATFORMS

AXIS_DEFAULT_HOST = '192.168.0.90'
AXIS_DEFAULT_USERNAME = 'root'
AXIS_DEFAULT_PASSWORD = 'pass'
DEFAULT_PORT = 80

DEVICE_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_HOST, default=AXIS_DEFAULT_HOST): cv.string,
    vol.Optional(CONF_USERNAME, default=AXIS_DEFAULT_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD, default=AXIS_DEFAULT_PASSWORD): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
}, extra=vol.ALLOW_EXTRA)


@callback
def configured_devices(hass):
    """Return a set of the configured devices."""
    return {entry.data[CONF_MAC]: entry for entry
            in hass.config_entries.async_entries(DOMAIN)}


@config_entries.HANDLERS.register(DOMAIN)
class AxisFlowHandler(config_entries.ConfigFlow):
    """Handle a Axis config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize the Axis config flow."""
        self.device_config = {}
        self.model = None
        self.name = None
        self.serial_number = None

        self.discovery_schema = {}
        self.import_schema = {}

    async def async_step_user(self, user_input=None):
        """Handle a Axis config flow start.

        Manage device specific parameters.
        """
        errors = {}

        if user_input is not None:
            try:
                self.device_config = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD]
                }
                device = await get_device(self.hass, self.device_config)

                self.serial_number = device.vapix.params.system_serialnumber

                if self.serial_number in configured_devices(self.hass):
                    raise AlreadyConfigured

                self.model = device.vapix.params.prodnbr

                return await self._create_entry()

            except AlreadyConfigured:
                errors['base'] = 'already_configured'

            except AuthenticationRequired:
                errors['base'] = 'faulty_credentials'

            except CannotConnect:
                errors['base'] = 'device_unavailable'

        data = self.import_schema or self.discovery_schema or {
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): int
        }

        return self.async_show_form(
            step_id='user',
            description_placeholders=self.device_config,
            data_schema=vol.Schema(data),
            errors=errors
        )

    async def _create_entry(self):
        """Create entry for device.

        Generate a name to be used as a prefix for device entities.
        """
        if self.name is None:
            same_model = [
                entry.data[CONF_NAME] for entry
                in self.hass.config_entries.async_entries(DOMAIN)
                if entry.data[CONF_MODEL] == self.model
            ]

            self.name = "{}".format(self.model)
            for idx in range(len(same_model) + 1):
                self.name = "{} {}".format(self.model, idx)
                if self.name not in same_model:
                    break

        data = {
            CONF_DEVICE: self.device_config,
            CONF_NAME: self.name,
            CONF_MAC: self.serial_number,
            CONF_MODEL: self.model,
        }

        title = "{} - {}".format(self.model, self.serial_number)
        return self.async_create_entry(
            title=title,
            data=data
        )

    async def _update_entry(self, entry, host):
        """Update existing entry if it is the same device."""
        entry.data[CONF_DEVICE][CONF_HOST] = host
        self.hass.config_entries.async_update_entry(entry)

    async def async_step_discovery(self, discovery_info):
        """Prepare configuration for a discovered Axis device.

        This flow is triggered by the discovery component.
        """
        if discovery_info[CONF_HOST].startswith('169.254'):
            return self.async_abort(reason='link_local_address')

        serialnumber = discovery_info['properties']['macaddress']
        device_entries = configured_devices(self.hass)

        if serialnumber in device_entries:
            entry = device_entries[serialnumber]
            await self._update_entry(entry, discovery_info[CONF_HOST])
            return self.async_abort(reason='already_configured')

        config_file = await self.hass.async_add_executor_job(
            load_json, self.hass.config.path(CONFIG_FILE))

        if serialnumber not in config_file:
            self.discovery_schema = {
                vol.Required(
                    CONF_HOST, default=discovery_info[CONF_HOST]): str,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_PORT, default=discovery_info[CONF_PORT]): int
            }
            return await self.async_step_user()

        try:
            device_config = DEVICE_SCHEMA(config_file[serialnumber])
            device_config[CONF_HOST] = discovery_info[CONF_HOST]

            if CONF_NAME not in device_config:
                device_config[CONF_NAME] = discovery_info['hostname']

        except vol.Invalid:
            return self.async_abort(reason='bad_config_file')

        return await self.async_step_import(device_config)

    async def async_step_import(self, import_config):
        """Import a Axis device as a config entry.

        This flow is triggered by `async_setup` for configured devices.
        This flow is also triggered by `async_step_discovery`.

        This will execute for any Axis device that contains a complete
        configuration.
        """
        self.name = import_config[CONF_NAME]

        self.import_schema = {
            vol.Required(CONF_HOST, default=import_config[CONF_HOST]): str,
            vol.Required(
                CONF_USERNAME, default=import_config[CONF_USERNAME]): str,
            vol.Required(
                CONF_PASSWORD, default=import_config[CONF_PASSWORD]): str,
            vol.Required(CONF_PORT, default=import_config[CONF_PORT]): int
        }
        return await self.async_step_user(user_input=import_config)
