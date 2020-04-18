"""Support for Xiomi Gateway alarm control panels."""

from functools import partial
import logging

from miio import DeviceException

from homeassistant.components.alarm_control_panel import (
    SUPPORT_ALARM_ARM_AWAY,
    AlarmControlPanel,
)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ["python-miio==0.5.0.1"]

XIAOMI_STATE_ARMED_VALUE = "on"
XIAOMI_STATE_DISARMED_VALUE = "off"
XIAOMI_STATE_ARMING_VALUE = "oning"
XIAOMI_SUCCESS = ["ok"]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Hue lights from a config entry."""
    devices = []
    gateway = hass.data[DOMAIN][config_entry.entry_id]
    device = XiaomiGatewayAlarm(
        gateway,
        config_entry.title + " Alarm",
        config_entry.data.get("model"),
        config_entry.data.get("mac"),
        config_entry.data.get("gateway_id"),
    )
    devices.append(device)
    async_add_entities(devices)


class XiaomiGatewayAlarm(AlarmControlPanel):
    """Representation of the XiaomiGatewayAlarm."""

    def __init__(self, gateway_device, gateway_name, model, mac_address, device_id):
        """Initialize the entity."""
        self._gateway = gateway_device
        self._name = gateway_name
        self._skip_update = False
        self._device_id = device_id
        self._unique_id = f"{model}-{mac_address}-alarm"
        self._icon = "mdi:shield-home"
        self._available = None
        self._state = None

    @property
    def should_poll(self):
        """Poll the miio device."""
        return True

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def device_id(self):
        """Return the device id of the gateway."""
        return self._device_id

    @property
    def device_info(self):
        """Return the device info of the gateway."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
        }

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
