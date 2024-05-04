"""Demo platform that offers a fake Date entity."""

from __future__ import annotations

from datetime import date

from homeassistant.components.date import DateEntity
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
    """Set up the demo date platform."""
    async_add_entities(
        [
            DemoDate(
                "date",
                "Date",
                date(2020, 1, 1),
                "mdi:calendar",
                False,
            ),
        ]
    )


class DemoDate(DateEntity):
    """Representation of a Demo date entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str,
        device_name: str,
        state: date,
        icon: str,
        assumed_state: bool,
    ) -> None:
        """Initialize the Demo date entity."""
        self._attr_assumed_state = assumed_state
        self._attr_icon = icon
        self._attr_native_value = state
        self._attr_unique_id = unique_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)}, name=device_name
        )

    async def async_set_value(self, value: date) -> None:
        """Update the date."""
        self._attr_native_value = value
        self.async_write_ha_state()
