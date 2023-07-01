"""Demo platform that offers a fake time entity."""
from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Demo time entity."""
    async_add_entities([DemoTime("time", "Time", time(12, 0, 0), "mdi:clock", False)])


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Demo config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


class DemoTime(TimeEntity):
    """Representation of a Demo time entity."""

    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str,
        name: str,
        state: time,
        icon: str,
        assumed_state: bool,
    ) -> None:
        """Initialize the Demo time entity."""
        self._attr_assumed_state = assumed_state
        self._attr_icon = icon
        self._attr_name = name or DEVICE_DEFAULT_NAME
        self._attr_native_value = state
        self._attr_unique_id = unique_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)}, name=self.name
        )

    async def async_set_value(self, value: time) -> None:
        """Update the time."""
        self._attr_native_value = value
        self.async_write_ha_state()
