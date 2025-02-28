"""Support for an Intergas boiler via an InComfort/Intouch Lan2RF gateway."""

from __future__ import annotations

import logging
from typing import Any

from incomfortclient import Heater as InComfortHeater

from homeassistant.components.water_heater import WaterHeaterEntity
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import InComfortConfigEntry, InComfortDataCoordinator
from .entity import IncomfortBoilerEntity

_LOGGER = logging.getLogger(__name__)

HEATER_ATTRS = ["display_code", "display_text", "is_burning"]

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InComfortConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up an InComfort/InTouch water_heater device."""
    incomfort_coordinator = entry.runtime_data
    heaters = incomfort_coordinator.data.heaters
    async_add_entities(IncomfortWaterHeater(incomfort_coordinator, h) for h in heaters)


class IncomfortWaterHeater(IncomfortBoilerEntity, WaterHeaterEntity):
    """Representation of an InComfort/Intouch water_heater device."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_min_temp = 30.0
    _attr_max_temp = 80.0
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = "boiler"

    def __init__(
        self, coordinator: InComfortDataCoordinator, heater: InComfortHeater
    ) -> None:
        """Initialize the water_heater device."""
        super().__init__(coordinator, heater)
        self._attr_unique_id = heater.serial_no

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        return {k: v for k, v in self._heater.status.items() if k in HEATER_ATTRS}

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self._heater.is_tapping:
            return self._heater.tap_temp
        if self._heater.is_pumping:
            return self._heater.heater_temp
        if self._heater.heater_temp is None:
            return self._heater.tap_temp
        if self._heater.tap_temp is None:
            return self._heater.heater_temp
        return max(self._heater.heater_temp, self._heater.tap_temp)

    @property
    def current_operation(self) -> str | None:
        """Return the current operation mode."""
        return self._heater.display_text
