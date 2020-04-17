"""Support for Xiomi Gateway alarm control panels."""

import asyncio
from functools import partial
import logging

from miio import DeviceException, gateway

from homeassistant.components.alarm_control_panel import (
    SUPPORT_ALARM_ARM_AWAY,
    AlarmControlPanel,
)
from homeassistant.const import (
    CONF_NAME,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
)
from homeassistant.exceptions import PlatformNotReady

from . import DOMAIN, CONF_GATEWAYS, KEY_GATEWAY_DEVICE, KEY_GATEWAY_INFO

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ["python-miio==0.5.0.1"]

ATTR_MODEL = "model"
ATTR_FIRMWARE_VERSION = "firmware_version"
ATTR_HARDWARE_VERSION = "hardware_version"

XIAOMI_STATE_ARMED_VALUE = "on"
XIAOMI_STATE_DISARMED_VALUE = "off"
XIAOMI_STATE_ARMING_VALUE = "oning"
XIAOMI_SUCCESS = ["ok"]


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Perform the setup for Xiaomi Miio devices."""
    for gw_device in hass.data[DOMAIN][CONF_GATEWAYS]:
        device = XiaomiGatewayAlarm(gw_device.get(KEY_GATEWAY_DEVICE), gw_device.get(CONF_NAME), gw_device.get(KEY_GATEWAY_INFO))
        add_entities([device], update_before_add=True)


class XiaomiGatewayAlarm(AlarmControlPanel):
    """Representation of the XiaomiGatewayAlarm."""

    def __init__(self, gateway_device, gateway_name, device_info):
        """Initialize the entity."""
        self._gateway = gateway_device
        self._name = gateway_name
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
        await self._try_command("Turning the alarm on failed.", self._gateway.alarm.on)

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
