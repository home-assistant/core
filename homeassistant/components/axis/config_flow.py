"""Config flow to configure Axis devices."""

from collections import OrderedDict

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    ATTR_LOCATION, CONF_DEVICE, CONF_HOST, CONF_INCLUDE, CONF_MAC, CONF_NAME,
    CONF_PASSWORD, CONF_PORT, CONF_TRIGGER_TIME, CONF_USERNAME)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.util.json import load_json

from .const import CONF_CAMERA, CONF_EVENTS, CONF_MODEL_ID, DOMAIN
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
DEFAULT_TRIGGER_TIME = 0

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_INCLUDE):
        vol.All(cv.ensure_list, [vol.In(AXIS_INCLUDE)]),
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_HOST, default=AXIS_DEFAULT_HOST): cv.string,
    vol.Optional(CONF_USERNAME, default=AXIS_DEFAULT_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD, default=AXIS_DEFAULT_PASSWORD): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(
        CONF_TRIGGER_TIME, default=DEFAULT_TRIGGER_TIME): cv.positive_int,
    vol.Optional(ATTR_LOCATION, default=''): cv.string,
})


@callback
def configured_devices(hass):
    """Return a set of the configured devices."""
    return set(entry.data[CONF_DEVICE][CONF_HOST] for entry
               in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class AxisFlowHandler(config_entries.ConfigFlow):
    """Handle a Axis config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize the Axis config flow."""
        self.device_config = {}
        self.camera = False
        self.events = []
        self.model_id = None
        self.name = None
        self.serial_number = None
        self.trigger_time = 0

        self.supports_video = False
        self.supported_events = ()

        self.discovery_schema = {}
        self.import_schema = {}

    async def async_step_user(self, user_input=None):
        """Handle a Axis config flow start.

        Manage device specific parameters.
        """
        from axis.event import device_events
        from axis.vapix import (
            VAPIX_IMAGE_FORMAT, VAPIX_MODEL_ID, VAPIX_SERIAL_NUMBER)
        errors = {}

        if user_input is not None:
            try:
                if user_input[CONF_HOST] in configured_devices(self.hass):
                    raise AlreadyConfigured

                self.device_config = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD]
                }
                device = await get_device(self.hass, self.device_config)

                self.serial_number = device.vapix.get_param(
                    VAPIX_SERIAL_NUMBER)
                self.model_id = device.vapix.get_param(VAPIX_MODEL_ID)

                if self.import_schema:
                    # Imported config is expected to have a working config
                    return await self._create_entry()

                supported_formats = device.vapix.get_param(VAPIX_IMAGE_FORMAT)
                self.supports_video = 'mjpeg' in supported_formats

                supported_events = await self.hass.async_add_executor_job(
                    device_events, device.config)
                self.supported_events = set(supported_events.keys())

                if self.supports_video or self.supported_events:
                    return await self.async_step_features()

            except AlreadyConfigured:
                errors['base'] = 'already_configured'

            except AuthenticationRequired:
                errors['base'] = 'faulty_credentials'

            except CannotConnect:
                errors['base'] = 'device_unavailable'

            else:
                errors['base'] = 'no_device_support'

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

    async def async_step_features(self, user_input=None):
        """What platforms and events to include with Axis devices."""
        errors = {}

        if user_input is not None:
            if self.supports_video:
                self.camera = user_input.pop(CONF_CAMERA)

                if self.camera and not any(user_input.values()):
                    # No events selected
                    return await self._create_entry()

            for event, selected in user_input.items():
                if selected:
                    self.events.append(event)

            if self.events:
                return await self.async_step_options()

            errors['base'] = 'no_feature'

        schema = OrderedDict()
        if self.supports_video:
            schema[vol.Optional(CONF_CAMERA, default=False)] = bool
        for event in sorted(self.supported_events):
            schema[vol.Optional(event, default=False)] = bool

        return self.async_show_form(
            step_id='features',
            data_schema=vol.Schema(schema),
            errors=errors
        )

    async def async_step_options(self, user_input=None):
        """Extra options for events from Axis device.

        CONF_TRIGGER_TIME -- Minimum time a sensor will be active.
        """
        errors = {}

        if user_input is not None:
            self.trigger_time = user_input[CONF_TRIGGER_TIME]
            return await self._create_entry()

        return self.async_show_form(
            step_id='options',
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_TRIGGER_TIME, default=DEFAULT_TRIGGER_TIME): int
            }),
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
                if entry.data[CONF_MODEL_ID] == self.model_id
            ]

            self.name = "{}".format(self.model_id)
            for idx in range(len(same_model) + 1):
                self.name = "{} {}".format(self.model_id, idx)
                if self.name not in same_model:
                    break

        data = {
            CONF_DEVICE: self.device_config,
            CONF_NAME: self.name,
            CONF_MAC: self.serial_number,
            CONF_MODEL_ID: self.model_id,
            CONF_CAMERA: self.camera,
            CONF_EVENTS: self.events,
            CONF_TRIGGER_TIME: self.trigger_time
        }

        desc = "{} - {}".format(self.model_id, self.serial_number)
        return self.async_create_entry(
            title=desc,
            data=data
        )

    async def async_step_discovery(self, discovery_info):
        """Prepare configuration for a discovered Axis device.

        This flow is triggered by the discovery component.
        """
        if discovery_info[CONF_HOST] in configured_devices(self.hass):
            return self.async_abort(reason='already_configured')

        if discovery_info[CONF_HOST].startswith('169.254'):
            return self.async_abort(reason='link_local_address')

        config_file = await self.hass.async_add_job(
            load_json, self.hass.config.path(CONFIG_FILE))

        serialnumber = discovery_info['properties']['macaddress']

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

        if CONF_CAMERA in import_config[CONF_INCLUDE]:
            self.camera = True
            import_config[CONF_INCLUDE].remove(CONF_CAMERA)

        self.events = import_config[CONF_INCLUDE]

        self.trigger_time = import_config[CONF_TRIGGER_TIME]

        self.import_schema = {
            vol.Required(CONF_HOST, default=import_config[CONF_HOST]): str,
            vol.Required(
                CONF_USERNAME, default=import_config[CONF_USERNAME]): str,
            vol.Required(
                CONF_PASSWORD, default=import_config[CONF_PASSWORD]): str,
            vol.Required(CONF_PORT, default=import_config[CONF_PORT]): int
        }
        return await self.async_step_user(user_input=import_config)
