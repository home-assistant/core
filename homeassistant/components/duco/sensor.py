"""Sensor platform for the Duco integration."""

from __future__ import annotations

from duco.models import Node, VentilationState

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DucoConfigEntry, DucoCoordinator
from .entity import DucoEntity

PARALLEL_UPDATES = 0

_STATE_TO_LEVEL: dict[VentilationState, str] = {
    VentilationState.EMPT: "off",
    VentilationState.AUTO: "auto",
    VentilationState.AUT1: "auto",
    VentilationState.AUT2: "auto",
    VentilationState.AUT3: "auto",
    VentilationState.CNT1: "1",
    VentilationState.MAN1: "1",
    VentilationState.MAN1x2: "1",
    VentilationState.MAN1x3: "1",
    VentilationState.CNT2: "2",
    VentilationState.MAN2: "2",
    VentilationState.MAN2x2: "2",
    VentilationState.MAN2x3: "2",
    VentilationState.CNT3: "3",
    VentilationState.MAN3: "3",
    VentilationState.MAN3x2: "3",
    VentilationState.MAN3x3: "3",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DucoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Duco sensor entities."""
    coordinator = entry.runtime_data

    async_add_entities(
        DucoVentilationLevelSensor(coordinator, node)
        for node in coordinator.data.values()
        if node.general.node_type == "BOX"
    )


class DucoVentilationLevelSensor(DucoEntity, SensorEntity):
    """Sensor showing the current ventilation level."""

    _attr_translation_key = "ventilation_level"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["off", "auto", "1", "2", "3"]

    def __init__(self, coordinator: DucoCoordinator, node: Node) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator, node)
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{node.node_id}_level"
        )

    @property
    def native_value(self) -> str | None:
        """Return the current ventilation level."""
        node = self._node
        if node.ventilation is None:
            return None
        return _STATE_TO_LEVEL.get(node.ventilation.state)
