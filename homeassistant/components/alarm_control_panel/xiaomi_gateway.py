"""
Support for Xiomi Gateway alarm control panels.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/
"""

import asyncio
from functools import partial
import loggingCONF_HOST

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA, )
from homeassistant.components.xiaomi_aqara import (CONF_HOST, CONF_TOKEN, )
from homeassistant.exceptions import PlatformNotReady
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED,
    STATE_UNKNOWN)


_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Xiaomi Gateway Alarm'
DATA_KEY = 'alarm_control_panel.xiaomi_gateway'

CONF_TURN_ON_COMMAND = 'set_arming'
CONF_TURN_ON_PARAMETERS = 'on'
CONF_TURN_OFF_COMMAND = 'set_arming'
CONF_TURN_OFF_PARAMETERS = 'off'
CONF_STATE_PROPERTY = 'get_arming'
CONF_STATE_ON_VALUE = 'on'
CONF_STATE_OFF_VALUE = 'off'
CONF_UPDATE_INSTANT = 'update_instant'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_TURN_ON_COMMAND, default='set_arming'): cv.string,
    vol.Optional(CONF_TURN_ON_PARAMETERS, default=['on']):
        vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_TURN_OFF_COMMAND, default='set_arming'): cv.string,
    vol.Optional(CONF_TURN_OFF_PARAMETERS, default=['off']):
        vol.All(cv.ensure_list, [cv.string]),
})

REQUIREMENTS = ['python-miio>=0.3.7']

ATTR_MODEL = 'model'
ATTR_FIRMWARE_VERSION = 'firmware_version'
ATTR_HARDWARE_VERSION = 'hardware_version'

SUCCESS = ['ok']


# pylint: disable=unused-argument
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):

    host = config.get(CONF_HOST)
    token = config.get(CONF_TOKEN)

    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])

    try:
        miio_device = Device(host, token)
        device_info = miio_device.info()
        model = device_info.model
        _LOGGER.info("%s %s %s detected",
                     model,
                     device_info.firmware_version,
                     device_info.hardware_version)

        device = XiaomiGateway(miio_device, config, device_info)
    except DeviceException:
        raise PlatformNotReady

    hass.data[DATA_KEY][host] = device
    async_add_devices([device], update_before_add=True)


class XiaomiGateway(alarm.AlarmControlPanel):
    """Representation of a Xiaomi Miio Generic Device."""

    def __init__(self, device, config, device_info):
        """Initialize the entity."""
        self._device = device

        self._name = config.get(CONF_NAME)
        self._turn_on_command = config.get(CONF_TURN_ON_COMMAND)
        self._turn_on_parameters = config.get(CONF_TURN_ON_PARAMETERS)
        self._turn_off_command = config.get(CONF_TURN_OFF_COMMAND)
        self._turn_off_parameters = config.get(CONF_TURN_OFF_PARAMETERS)
        self._state_property = config.get(CONF_STATE_PROPERTY)
        self._state_on_value = config.get(CONF_STATE_ON_VALUE)
        self._state_off_value = config.get(CONF_STATE_OFF_VALUE)
        self._update_instant = config.get(CONF_UPDATE_INSTANT)
        self._skip_update = False

        self._model = device_info.model
        self._unique_id = "{}-{}-{}".format(device_info.model,
                                            device_info.mac_address,
                                            self._state_property)
        self._icon = 'mdi:flask-outline'

        self._available = None
        self._state = None
        self._state_attrs = {
            ATTR_MODEL: self._model,
            ATTR_FIRMWARE_VERSION: device_info.firmware_version,
            ATTR_HARDWARE_VERSION: device_info.hardware_version,
            ATTR_STATE_PROPERTY: self._state_property
        }

    @property
    def should_poll(self):
        """Poll the miio device."""
        return True

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of this entity, if any."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return self._icon

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    async def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a device command handling error messages."""
        from miio import DeviceException
        try:
            result = await self.hass.async_add_job(
                partial(func, *args, **kwargs))

            _LOGGER.info("Response received from miio device: %s", result)

            return result == SUCCESS
        except DeviceException as exc:
            _LOGGER.error(mask_error, exc)
            return False

    async def alarm_arm_away(self, **kwargs):
        """Turn on."""
        result = await self._try_command(
            "Turning the miio device on failed.", self._device.send,
            self._turn_on_command, self._turn_on_parameters)

        if result:
            self._state = True
            self._skip_update = True

    async def alarm_disarm(self, **kwargs):
        """Turn off."""
        result = await self._try_command(
            "Turning the miio device off failed.", self._device.send,
            self._turn_off_command, self._turn_off_parameters)

        if result:
            self._state = False
            self._skip_update = True

    async def async_update(self):
        """Fetch state from the device."""
        from miio import DeviceException

        # On state change some devices doesn't provide the new state immediately.
        if self._update_instant is False and self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_job(
                self._device.send, 'get_arming', [self._state_property])
            state = state.pop()

            _LOGGER.debug("Got new state: %s", state)

            self._available = True

            if state == self._state_on_value:
                self._state = STATE_ALARM_ARMED_AWAY
            elif state == self._state_off_value:
                self._state = STATE_ALARM_DISARMED
            else:
                _LOGGER.warning(
                    "New state (%s) doesn't match expected values: %s/%s",
                    state, self._state_on_value, self._state_off_value)
                self._state = None

            self._state_attrs.update({
                ATTR_STATE_VALUE: state
            })

        except DeviceException as ex:
            self._available = False
            _LOGGER.error("Got exception while fetching the state: %s", ex)

