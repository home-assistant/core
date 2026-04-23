"""Support for rain sensors built into some Velux windows."""

from __future__ import annotations

from pyvlx import Window

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import VeluxConfigEntry
from .coordinator import VeluxLimitationCoordinator
from .entity import velux_device_info, velux_unique_id

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VeluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up rain sensor(s) for Velux platform."""
    pyvlx = config_entry.runtime_data.pyvlx
    limitation_coordinators = config_entry.runtime_data.limitation_coordinators

    async_add_entities(
        VeluxRainSensor(limitation_coordinators[node.node_id], config_entry.entry_id)
        for node in pyvlx.nodes
        if isinstance(node, Window) and node.rain_sensor
    )


class VeluxRainSensor(
    CoordinatorEntity[VeluxLimitationCoordinator], BinarySensorEntity
):
    """Representation of a Velux rain sensor."""

    _attr_entity_registry_enabled_default = False
    _attr_device_class = BinarySensorDeviceClass.MOISTURE
    _attr_translation_key = "rain_sensor"
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: VeluxLimitationCoordinator, config_entry_id: str
    ) -> None:
        """Initialize VeluxRainSensor."""
        super().__init__(coordinator)
        node = coordinator.node
        unique_id = velux_unique_id(node, config_entry_id)
        self._attr_unique_id = f"{unique_id}_rain_sensor"
        self._attr_device_info = velux_device_info(node, config_entry_id)

    @property
    def is_on(self) -> bool:
        """Return true if rain is detected."""
        # Velux windows with rain sensors report an opening limitation when rain is detected.
        # So far we've seen 89, 91, 93 (most cases) or 100 (Velux GPU). It probably makes sense to
        # assume that any large enough limitation (we use >=89) means rain is detected.
        # Documentation on this is non-existent AFAIK.
        return self.coordinator.data.min.position_percent >= 89
