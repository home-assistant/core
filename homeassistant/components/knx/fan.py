"""Support for KNX/IP fans."""
from xknx.devices import Fan as XknxFan

from typing import TYPE_CHECKING, Any, Iterator, Optional

from homeassistant.components.fan import (
    FanEntity,
)

from .const import DOMAIN
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

    @property
    def speed(self) -> Optional[str]:
        """Return the current speed."""
        return self._device.current_speed

    async def async_set_speed(self, speed: str):
        self._device.set_speed()