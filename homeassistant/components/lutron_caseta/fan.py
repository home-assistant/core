"""Support for Lutron Caseta fans."""
import logging

from homeassistant.components.fan import (
    SUPPORT_SET_SPEED, FanEntity, DOMAIN)

from . import LUTRON_CASETA_SMARTBRIDGE, LutronCasetaDevice

_LOGGER = logging.getLogger(__name__)

LUTRON_SPEED_OFF = 'Off'
LUTRON_SPEED_LOW = 'Low'
LUTRON_SPEED_MEDIUM = 'Medium'
LUTRON_SPEED_MEDIUMHIGH = "MediumHigh"
LUTRON_SPEED_HIGH = 'High'


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up Lutron fan."""
    devs = []
    bridge = hass.data[LUTRON_CASETA_SMARTBRIDGE]
    fan_devices = bridge.get_devices_by_domain(DOMAIN)

    for fan_device in fan_devices:
        dev = LutronCasetaFan(fan_device, bridge)
        devs.append(dev)

    async_add_entities(devs, True)
    return True


class LutronCasetaFan(LutronCasetaDevice, FanEntity):
    """Representation of a Lutron Caseta fan. Including Fan Speed."""

    @property
    def speed(self) -> str:
        """Return the current speed."""
        return self._speed

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds.

        Note: The default Hass Speeds were all lower case
        and missing MediumHigh. Lutron Case and fan
        speeds specified instead.
        """
        return [LUTRON_SPEED_OFF, LUTRON_SPEED_LOW, LUTRON_SPEED_MEDIUM,
            LUTRON_SPEED_MEDIUMHIGH, LUTRON_SPEED_HIGH]

    @property
    def supported_features(self) -> int:
        """Flag supported features. Speed Only."""
        return SUPPORT_SET_SPEED

    async def async_turn_on(self, speed: str = None, **kwargs):
        """Turn the fan on."""
        if speed is None:
            speed = LUTRON_SPEED_MEDIUMHIGH
        await self.async_set_speed(speed)

    async def async_turn_off(self, **kwargs):
        """Turn the fan off."""
        await self.async_set_speed(LUTRON_SPEED_OFF)

    async def async_set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        self._speed = speed
        self._smartbridge.set_fan(self._device_id, self._speed)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state["fan_speed"] in [LUTRON_SPEED_LOW,
            LUTRON_SPEED_MEDIUM, LUTRON_SPEED_MEDIUMHIGH,
            LUTRON_SPEED_HIGH]

    async def async_update(self):
        """Update when forcing a refresh of the device."""
        self._state = self._smartbridge.get_device_by_id(self._device_id)
        self._speed = self._state["fan_speed"]
        _LOGGER.debug("State of this lutron fan device is %s", self._state)