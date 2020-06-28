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
FAN_SPEEDS = [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]
SPEED_TO_VALUE = {
    SPEED_OFF: FanSpeed.OFF,
    SPEED_LOW: FanSpeed.LOW,
    SPEED_MEDIUM: FanSpeed.MEDIUM,
    SPEED_HIGH: FanSpeed.HIGH,
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the INSTEON entity class for the hass platform."""
    async_add_insteon_entities(
        hass, DOMAIN, InsteonFanEntity, async_add_entities, discovery_info
    )


class InsteonFanEntity(InsteonEntity, FanEntity):
    """An INSTEON fan entity."""

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
        return FAN_SPEEDS

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED

    async def async_turn_on(self, speed: str = None, **kwargs) -> None:
        """Turn on the fan."""
        if speed is None:
            speed = SPEED_MEDIUM
        await self.async_set_speed(speed)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the fan."""
        await self._insteon_device.async_fan_off()

    async def async_set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        fan_speed = SPEED_TO_VALUE[speed]
        if fan_speed == FanSpeed.OFF:
            await self._insteon_device.async_fan_off()
        else:
            await self._insteon_device.async_fan_on(on_level=fan_speed)
