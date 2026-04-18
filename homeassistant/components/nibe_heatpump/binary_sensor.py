"""The Nibe Heat Pump binary sensors."""

from __future__ import annotations

from nibe.coil import Coil, CoilData

from homeassistant.components.binary_sensor import ENTITY_ID_FORMAT, BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import CoilCoordinator, NibeHeatpumpConfigEntry
from .entity import CoilEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NibeHeatpumpConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up platform."""

    coordinator = config_entry.runtime_data

    async_add_entities(
        BinarySensor(coordinator, coil)
        for coil in coordinator.coils
        if not coil.is_writable and coil.is_boolean
    )


class BinarySensor(CoilEntity, BinarySensorEntity):
    """Binary sensor entity."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: CoilCoordinator, coil: Coil) -> None:
        """Initialize entity."""
        super().__init__(coordinator, coil, ENTITY_ID_FORMAT)
        self._on_value = coil.get_mapping_for(1)

    def _async_read_coil(self, data: CoilData) -> None:
        self._attr_is_on = data.value == self._on_value
