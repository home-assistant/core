"""Demo platform that offers a fake date/time entity."""

from __future__ import annotations

from datetime import UTC, datetime

from homeassistant.components.datetime import DateTimeEntity
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
    """Set up the demo datetime platform."""
    async_add_entities(
        [
            DemoDateTime(
                "datetime",
                "Date and Time",
                datetime(2020, 1, 1, 12, 0, 0, tzinfo=UTC),
                "mdi:calendar-clock",
                False,
            ),
        ]
    )


class DemoDateTime(DateTimeEntity):
    """Representation of a Demo date/time entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str,
        device_name: str,
        state: datetime,
        icon: str,
        assumed_state: bool,
    ) -> None:
        """Initialize the Demo date/time entity."""
        self._attr_assumed_state = assumed_state
        self._attr_icon = icon
        self._attr_native_value = state
        self._attr_unique_id = unique_id

        self._attr_device_info = DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, unique_id)
            },
            name=device_name,
        )

    async def async_set_value(self, value: datetime) -> None:
        """Update the date/time."""
        self._attr_native_value = value
        self.async_write_ha_state()
