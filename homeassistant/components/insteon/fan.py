"""Support for INSTEON fans via PowerLinc Modem."""
import math

from pyinsteon.constants import FanSpeed

from homeassistant.components.fan import (
    DOMAIN as FAN_DOMAIN,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import SIGNAL_ADD_ENTITIES
from .insteon_entity import InsteonEntity
from .utils import async_add_insteon_entities

SPEED_RANGE = (1, FanSpeed.HIGH)  # off is not included


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Insteon fans from a config entry."""

    def add_entities(discovery_info=None):
        """Add the Insteon entities for the platform."""
        async_add_insteon_entities(
            hass, FAN_DOMAIN, InsteonFanEntity, async_add_entities, discovery_info
        )

    signal = f"{SIGNAL_ADD_ENTITIES}_{FAN_DOMAIN}"
    async_dispatcher_connect(hass, signal, add_entities)
    add_entities()


class InsteonFanEntity(InsteonEntity, FanEntity):
    """An INSTEON fan entity."""

    @property
    def percentage(self) -> str:
        """Return the current speed percentage."""
        if self._insteon_device_group.value is None:
            return None
        return ranged_value_to_percentage(SPEED_RANGE, self._insteon_device_group.value)

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED

    async def async_turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs,
    ) -> None:
        """Turn on the fan."""
        if percentage is None:
            percentage = 50
        await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the fan."""
        await self._insteon_device.async_fan_off()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            await self._insteon_device.async_fan_off()
        else:
            on_level = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
            await self._insteon_device.async_fan_on(on_level=on_level)
