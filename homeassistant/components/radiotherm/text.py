"""Support for Radio Thermostat text entities."""

from __future__ import annotations

import json

import radiotherm.thermostat

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import RadioThermUpdateCoordinator
from .entity import RadioThermostatEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up text entities for a radiotherm device."""
    coordinator: RadioThermUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    if not isinstance(coordinator.init_data.tstat, radiotherm.thermostat.CT80):
        return

    async_add_entities(
        [
            RadioThermUMAText(coordinator, entry, line=0),
            RadioThermUMAText(coordinator, entry, line=1),
        ]
    )


class RadioThermUMAText(RadioThermostatEntity, TextEntity):
    """Text entity for CT80 User Messaging Area line."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: RadioThermUpdateCoordinator,
        entry: ConfigEntry,
        line: int,
    ) -> None:
        """Initialize the UMA text entity."""
        super().__init__(coordinator)
        self._line = line
        self._attr_name = f"User Messaging Area {line}"
        self._attr_unique_id = f"{coordinator.init_data.mac}_uma_line{line}"
        self._attr_native_value = ""

    def _process_data(self) -> None:
        """No coordinator state to process for UMA."""

    async def async_set_value(self, value: str) -> None:
        """Set the UMA message on the thermostat."""
        await self.hass.async_add_executor_job(self._set_uma_message, value)
        self._attr_native_value = value
        self.async_write_ha_state()

    def _set_uma_message(self, message: str) -> None:
        """Set the UMA message on the device."""

        # Setting an empty message is ignored by the thermostat.
        if not message:
            message = " "

        # There is only space for 26 characters.
        if len(message) > 26:
            message = message[:26]

        self.device.post(
            "/tstat/uma",
            json.dumps({"line": self._line, "message": message}).encode("utf-8"),
        )
