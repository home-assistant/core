"""Support for INSTEON fans via PowerLinc Modem."""
import logging

from pyinsteon.constants import FanSpeed

from homeassistant.components.fan import (
    DOMAIN,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_SET_SPEED,
    FanEntity,
)

from .insteon_entity import InsteonEntity
from .utils import async_add_insteon_entities

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the INSTEON device class for the hass platform."""
    async_add_insteon_entities(
        hass, DOMAIN, InsteonFan, async_add_entities, discovery_info
    )


class InsteonFan(InsteonEntity, FanEntity):
    """An INSTEON fan component."""

    @property
    def speed(self) -> str:
        """Return the current speed."""
        if self._insteon_device_group.value == FanSpeed.HIGH:
            return SPEED_HIGH
        if self._insteon_device_group.value == FanSpeed.MEDIUM:
            return SPEED_MEDIUM
        if self._insteon_device_group.value == FanSpeed.LOW:
            return SPEED_LOW
        return SPEED_OFF

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return [str(speed) for speed in FanSpeed]

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED

    async def async_turn_on(self, speed: str = None, **kwargs) -> None:
        """Turn on the entity."""
        if speed is None:
            speed = str(FanSpeed.MEDIUM)
        await self.async_set_speed(speed)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the entity."""
        await self.async_set_speed(str(FanSpeed.OFF))

    async def async_set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        fan_speed = getattr(FanSpeed, speed.upper())
        if fan_speed == FanSpeed.OFF:
            self._insteon_device.fan_off()
        else:
            self._insteon_device.fan_on(on_level=fan_speed)
