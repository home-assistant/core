"""Sensor platform for the Duco integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from duco.models import Node, NodeType, VentilationState

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CONCENTRATION_PARTS_PER_MILLION, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DucoConfigEntry, DucoCoordinator
from .entity import DucoEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class DucoSensorEntityDescription(SensorEntityDescription):
    """Duco sensor entity description."""

    value_fn: Callable[[Node], int | float | str | None]
    node_types: tuple[NodeType, ...]


SENSOR_DESCRIPTIONS: tuple[DucoSensorEntityDescription, ...] = (
    DucoSensorEntityDescription(
        key="ventilation_state",
        translation_key="ventilation_state",
        device_class=SensorDeviceClass.ENUM,
        options=[s.lower() for s in VentilationState],
        value_fn=lambda node: (
            node.ventilation.state.lower() if node.ventilation else None
        ),
        node_types=(NodeType.BOX,),
    ),
    DucoSensorEntityDescription(
        key="co2",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        value_fn=lambda node: node.sensor.co2 if node.sensor else None,
        node_types=(NodeType.UCCO2,),
    ),
    DucoSensorEntityDescription(
        key="iaq_co2",
        translation_key="iaq_co2",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda node: node.sensor.iaq_co2 if node.sensor else None,
        node_types=(NodeType.UCCO2,),
    ),
    DucoSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda node: node.sensor.rh if node.sensor else None,
        node_types=(NodeType.BSRH,),
    ),
    DucoSensorEntityDescription(
        key="iaq_rh",
        translation_key="iaq_rh",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda node: node.sensor.iaq_rh if node.sensor else None,
        node_types=(NodeType.BSRH,),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DucoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Duco sensor entities."""
    coordinator = entry.runtime_data

    async_add_entities(
        DucoSensorEntity(coordinator, node, description)
        for node in coordinator.data.values()
        for description in SENSOR_DESCRIPTIONS
        if node.general.node_type in description.node_types
    )


class DucoSensorEntity(DucoEntity, SensorEntity):
    """Sensor entity for a Duco node."""

    entity_description: DucoSensorEntityDescription

    def __init__(
        self,
        coordinator: DucoCoordinator,
        node: Node,
        description: DucoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator, node)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{node.node_id}_{description.key}"
        )

    @property
    def native_value(self) -> int | float | str | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self._node)
