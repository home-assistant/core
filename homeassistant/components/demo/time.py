"""Demo platform that offers a fake time entity."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the demo time platform."""
    async_add_entities([DemoTime("time", "Time", time(12, 0, 0), False)])


class DemoTime(TimeEntity):
    """Representation of a Demo time entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str,
        device_name: str,
        state: time,
        assumed_state: bool,
    ) -> None:
        """Initialize the Demo time entity."""
        self._attr_assumed_state = assumed_state
        self._attr_native_value = state
        self._attr_unique_id = unique_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)}, name=device_name
        )

    async def async_set_value(self, value: time) -> None:
        """Update the time."""
        self._attr_native_value = value
        self.async_write_ha_state()
