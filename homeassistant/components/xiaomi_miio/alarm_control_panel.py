"""
Support for Xiomi Gateway alarm control panels.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/
"""

import asyncio
from functools import partial
import logging

import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanel,
    PLATFORM_SCHEMA,
    SUPPORT_ALARM_ARM_AWAY,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.exceptions import PlatformNotReady
from homeassistant.const import (
    CONF_NAME,
    CONF_HOST,
    CONF_TOKEN,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_DISARMED,
    STATE_ALARM_ARMING,
)

from miio import Device, DeviceException, gateway

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Xiaomi Gateway Alarm"
DATA_KEY = "alarm_control_panel.xiaomi_gateway"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

REQUIREMENTS = ["python-miio==0.4.8"]

ATTR_MODEL = "model"
ATTR_FIRMWARE_VERSION = "firmware_version"
ATTR_HARDWARE_VERSION = "hardware_version"

XIAOMI_STATE_ARMED_VALUE = "on"
XIAOMI_STATE_DISARMED_VALUE = "off"
XIAOMI_STATE_ARMING_VALUE = "oning"
XIAOMI_SUCCESS = ["ok"]


# pylint: disable=unused-argument
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the sensor from config."""
    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}
    host = config.get(CONF_HOST)
    token = config.get(CONF_TOKEN)
    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])

    try:
        miio_device = Device(host, token)
        device_info = miio_device.info()
        model = device_info.model
        _LOGGER.info(
            "%s %s %s detected",
            model,
            device_info.firmware_version,
            device_info.hardware_version,
        )

        gateway_device = gateway.Gateway(miio_device)
        device = XiaomiGatewayAlarm(gateway_device, config, device_info)
    except DeviceException:
        raise PlatformNotReady

    hass.data[DATA_KEY][host] = device
    async_add_devices([device], update_before_add=True)


class XiaomiGatewayAlarm(AlarmControlPanel):
    """Representation of the XiaomiGatewayAlarm."""

    def __init__(self, gateway_device, config, device_info):
        """Initialize the entity."""
        self._gateway = gateway_device
        self._name = config.get(CONF_NAME)
        self._skip_update = False
        self._model = device_info.model
        self._unique_id = "{}-{}-alarm".format(
            device_info.model, device_info.mac_address
        )
        self._icon = "mdi:shield-home"
        self._available = None
        self._state = None
        self._state_attrs = {
            ATTR_MODEL: self._model,
            ATTR_FIRMWARE_VERSION: device_info.firmware_version,
            ATTR_HARDWARE_VERSION: device_info.hardware_version,
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
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_AWAY

    async def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a device command handling error messages."""
        try:
            result = await self.hass.async_add_job(partial(func, *args, **kwargs))

            _LOGGER.info("Response received from miio device: %s", result)

            return result == XIAOMI_SUCCESS
        except DeviceException as exc:
            _LOGGER.error(mask_error, exc)
            return False

    async def async_alarm_arm_away(self, code=None):
        """Turn on."""
        await self._try_command(
            "Turning the alarm on failed.", self._gateway.alarm.on
        )

    async def async_alarm_disarm(self, code=None):
        """Turn off."""
        await self._try_command(
            "Turning the alarm off failed.", self._gateway.alarm.off
        )

    async def async_update(self):
        """Fetch state from the device."""
        # On state change some devices doesn't provide the new
        # state immediately.
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_job(self._gateway.alarm.status)

            _LOGGER.debug("Got new state: %s", state)

            self._available = True

            if state == XIAOMI_STATE_ARMED_VALUE:
                self._state = STATE_ALARM_ARMED_AWAY
            elif state == XIAOMI_STATE_DISARMED_VALUE:
                self._state = STATE_ALARM_DISARMED
            elif state == XIAOMI_STATE_ARMING_VALUE:
                self._state = STATE_ALARM_ARMING
            else:
                _LOGGER.warning(
                    "New state (%s) doesn't match expected values: %s/%s/%s",
                    state,
                    XIAOMI_STATE_ARMED_VALUE,
                    XIAOMI_STATE_DISARMED_VALUE,
                    XIAOMI_STATE_ARMING_VALUE,
                )
                self._state = None

            _LOGGER.debug("State value: %s", self._state)
        except DeviceException as ex:
            self._available = False
            _LOGGER.error("Got exception while fetching the state: %s", ex)
