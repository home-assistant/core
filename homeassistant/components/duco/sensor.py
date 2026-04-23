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
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import DucoConfigEntry, DucoCoordinator
from .entity import DucoEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class DucoSensorEntityDescription(SensorEntityDescription):
    """Duco sensor entity description."""

    value_fn: Callable[[Node], int | float | str | None]
    node_types: tuple[NodeType, ...]


@dataclass(frozen=True, kw_only=True)
class DucoBoxSensorEntityDescription(SensorEntityDescription):
    """Duco sensor entity description for box-level diagnostic data."""

    value_fn: Callable[[DucoCoordinator], int | float | None]


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

BOX_SENSOR_DESCRIPTIONS: tuple[DucoBoxSensorEntityDescription, ...] = (
    DucoBoxSensorEntityDescription(
        key="rssi_wifi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda coordinator: coordinator.data.rssi_wifi,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DucoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Duco sensor entities."""
    coordinator = entry.runtime_data

    # Track the node IDs for which entities have already been created, so we
    # can detect both newly added and stale (deregistered) nodes on every
    # coordinator update.
    known_nodes: set[int] = set()

    @callback
    def _async_add_new_entities() -> None:
        # Remove devices whose nodes have disappeared from the API.
        # The firmware removes deregistered RF/wired nodes automatically.
        # BSRH box sensors that are physically unplugged from the PCB are
        # not deregistered by the firmware and will never appear here as stale.
        stale_node_ids = known_nodes - coordinator.data.nodes.keys()
        if stale_node_ids:
            device_reg = dr.async_get(hass)
            mac = entry.unique_id
            for node_id in stale_node_ids:
                device = device_reg.async_get_device(
                    identifiers={(DOMAIN, f"{mac}_{node_id}")}
                )
                if device:
                    device_reg.async_update_device(
                        device.id,
                        remove_config_entry_id=entry.entry_id,
                    )
            known_nodes.difference_update(stale_node_ids)

        new_entities: list[SensorEntity] = []
        for node in coordinator.data.nodes.values():
            if node.node_id in known_nodes:
                continue
            known_nodes.add(node.node_id)
            new_entities.extend(
                DucoSensorEntity(coordinator, node, description)
                for description in SENSOR_DESCRIPTIONS
                if node.general.node_type in description.node_types
            )
            new_entities.extend(
                DucoBoxSensorEntity(coordinator, node, description)
                for description in BOX_SENSOR_DESCRIPTIONS
                if node.general.node_type == NodeType.BOX
            )
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_entities))
    _async_add_new_entities()


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


class DucoBoxSensorEntity(DucoEntity, SensorEntity):
    """Sensor entity for box-level diagnostic data."""

    entity_description: DucoBoxSensorEntityDescription

    def __init__(
        self,
        coordinator: DucoCoordinator,
        node: Node,
        description: DucoBoxSensorEntityDescription,
    ) -> None:
        """Initialize the box sensor entity."""
        super().__init__(coordinator, node)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{node.node_id}_{description.key}"
        )

    @property
    def native_value(self) -> int | float | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator)
