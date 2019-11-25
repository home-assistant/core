"""Support for Lutron Caseta fans."""
import logging

from pylutron_caseta import FAN_OFF, FAN_LOW, FAN_MEDIUM, FAN_HIGH

from homeassistant.components.fan import (
    SUPPORT_SET_SPEED,
    FanEntity,
    DOMAIN,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
)

from . import LUTRON_CASETA_SMARTBRIDGE, LutronCasetaDevice

_LOGGER = logging.getLogger(__name__)

VALUE_TO_SPEED = {
    None: SPEED_OFF,
    FAN_OFF: SPEED_OFF,
    FAN_LOW: SPEED_LOW,
    FAN_MEDIUM: SPEED_MEDIUM,
    FAN_HIGH: SPEED_HIGH,
}

SPEED_TO_VALUE = {
    SPEED_OFF: FAN_OFF,
    SPEED_LOW: FAN_LOW,
    SPEED_MEDIUM: FAN_MEDIUM,
    SPEED_HIGH: FAN_HIGH,
}

FAN_SPEEDS = [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up Lutron fan."""
    devs = []
    bridge = hass.data[LUTRON_CASETA_SMARTBRIDGE]
    fan_devices = bridge.get_devices_by_domain(DOMAIN)

    for fan_device in fan_devices:
        dev = LutronCasetaFan(fan_device, bridge)
        devs.append(dev)

    async_add_entities(devs, True)


class LutronCasetaFan(LutronCasetaDevice, FanEntity):
    """Representation of a Lutron Caseta fan. Including Fan Speed."""

    @property
    def speed(self) -> str:
        """Return the current speed."""
        return VALUE_TO_SPEED[self._state["fan_speed"]]

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return FAN_SPEEDS

    @property
    def supported_features(self) -> int:
        """Flag supported features. Speed Only."""
        return SUPPORT_SET_SPEED

    async def async_turn_on(self, speed: str = None, **kwargs):
        """Turn the fan on."""
        if speed is None:
            speed = SPEED_MEDIUM
        await self.async_set_speed(speed)

    async def async_turn_off(self, **kwargs):
        """Turn the fan off."""
        await self.async_set_speed(SPEED_OFF)

    async def async_set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        self._smartbridge.set_fan(self._device_id, SPEED_TO_VALUE[speed])

    @property
    def is_on(self):
        """Return true if device is on."""
        return VALUE_TO_SPEED[self._state["fan_speed"]] in [
            SPEED_LOW,
            SPEED_MEDIUM,
            SPEED_HIGH,
        ]

    async def async_update(self):
        """Update when forcing a refresh of the device."""
        self._state = self._smartbridge.get_device_by_id(self._device_id)
        _LOGGER.debug("State of this lutron fan device is %s", self._state)
        