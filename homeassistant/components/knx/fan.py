"""Support for KNX/IP fans."""
from xknx.devices import Fan as XknxFan

from typing import TYPE_CHECKING, Any, Iterator, Optional

from homeassistant.components.fan import (
    FanEntity,
    SPEED_OFF,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_HIGH,
    SUPPORT_SET_SPEED,
)

from .const import DOMAIN
from .schema import FanSchema
from .knx_entity import KnxEntity


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up fans for KNX platform."""
    entities = []
    for device in hass.data[DOMAIN].xknx.devices:
        if isinstance(device, XknxFan):
            entities.append(KNXFan(device))
    async_add_entities(entities)


class KNXFan(KnxEntity, FanEntity):
    """Representation of a KNX fan."""

    def __init__(self, device: XknxFan):
        """Initialize of KNX fan."""
        super().__init__(device)
        # TODO: REMOVE
        self._device = device
        self._ha_to_knx_value = self._device.speed_mapping
        self._knx_to_ha_value = {v: k for k, v in self._ha_to_knx_value.items()}

    @property
    def speed(self) -> Optional[str]:
        """Return the current speed."""
        if self._device.current_speed in self._knx_to_ha_value:
            return self._knx_to_ha_value[self._device.current_speed]
        return None

    async def async_set_speed(self, speed: str):
        # await self._device.set_speed(self._ha_to_knx_value[speed])
        await self._device.set_speed(2)

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return self._device.speed_list

    async def async_turn_on(self, speed: str = None, **kwargs) -> None:
        await self.async_set_speed(speed)

    async def async_turn_off(self, **kwargs) -> None:
        await self.async_set_speed(SPEED_OFF)