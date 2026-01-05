"""Support for Broadlink selects."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BroadlinkDevice
from .const import DOMAIN
from .entity import BroadlinkEntity

DAY_ID_TO_NAME = {
    1: "monday",
    2: "tuesday",
    3: "wednesday",
    4: "thursday",
    5: "friday",
    6: "saturday",
    7: "sunday",
}
DAY_NAME_TO_ID = {v: k for k, v in DAY_ID_TO_NAME.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Broadlink select."""
    device = hass.data[DOMAIN].devices[config_entry.entry_id]
    async_add_entities([BroadlinkDayOfWeek(device)])


class BroadlinkDayOfWeek(BroadlinkEntity, SelectEntity):
    """Representation of a Broadlink day of week."""

    _attr_has_entity_name = True
    _attr_current_option: str | None = None
    _attr_options = list(DAY_NAME_TO_ID)
    _attr_translation_key = "day_of_week"

    def __init__(self, device: BroadlinkDevice) -> None:
        """Initialize the select."""
        super().__init__(device)

        self._attr_unique_id = f"{device.unique_id}-dayofweek"

    def _update_state(self, data: dict[str, Any]) -> None:
        """Update the state of the entity."""
        if data is None or "dayofweek" not in data:
            self._attr_current_option = None
        else:
            self._attr_current_option = DAY_ID_TO_NAME[data["dayofweek"]]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self._device.async_request(
            self._device.api.set_time,
            hour=self._coordinator.data["hour"],
            minute=self._coordinator.data["min"],
            second=self._coordinator.data["sec"],
            day=DAY_NAME_TO_ID[option],
        )
        self._attr_current_option = option
        self.async_write_ha_state()
