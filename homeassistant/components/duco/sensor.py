"""Sensor platform for the Duco integration."""

from __future__ import annotations

from duco.models import Node

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import DucoConfigEntry, DucoCoordinator
from .entity import DucoEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DucoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Duco sensor entities."""
    coordinator = entry.runtime_data

    async_add_entities(
        DucoVentilationStateSensor(coordinator, node)
        for node in coordinator.data
        if node.ventilation is not None
    )


class DucoVentilationStateSensor(DucoEntity, SensorEntity):
    """Sensor entity showing the raw Duco ventilation state."""

    _attr_translation_key = "ventilation_state"

    def __init__(self, coordinator: DucoCoordinator, node: Node) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator, node.node_id)
        mac = coordinator.config_entry.unique_id
        self._attr_unique_id = f"{mac}_{node.node_id}_ventilation_state"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{mac}_{node.node_id}")},
            manufacturer="Duco",
            model=coordinator.board_info.box_name
            if node.general.node_type == "BOX"
            else node.general.node_type,
            name=node.general.name or f"Node {node.node_id}",
        )

    @property
    def native_value(self) -> str | None:
        """Return the current ventilation state."""
        node = self._node
        if node is None or node.ventilation is None:
            return None
        return node.ventilation.state
