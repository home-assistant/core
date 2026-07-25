"""Sensor platform for the Duco integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import override

from duco_connectivity.models import Node, NodeType, VentilationState

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfRatio,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import BOX_NODE_ID, DOMAIN, VENTILATION_CAPABLE_NODE_TYPES
from .coordinator import DucoConfigEntry, DucoCoordinator
from .entity import DucoEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class DucoSensorEntityDescription(SensorEntityDescription):
    """Duco sensor entity description."""

    value_fn: Callable[[Node], datetime | int | float | str | None]
    node_types: tuple[NodeType, ...]


@dataclass(frozen=True, kw_only=True)
class DucoBoxSensorEntityDescription(SensorEntityDescription):
    """Duco sensor entity description for box-level diagnostic data."""

    supported_fn: Callable[[DucoCoordinator], bool] = lambda _: True
    value_fn: Callable[[DucoCoordinator], int | float | None]


SENSOR_DESCRIPTIONS: tuple[DucoSensorEntityDescription, ...] = (
    DucoSensorEntityDescription(
        key="ventilation_state",
        translation_key="ventilation_state",
        device_class=SensorDeviceClass.ENUM,
        options=[
            state.lower()
            for state in VentilationState
            if state != VentilationState.UNKNOWN
        ],
        value_fn=lambda node: (
            node.ventilation.state.lower()
            if node.ventilation and node.ventilation.state != VentilationState.UNKNOWN
            else None
        ),
        node_types=VENTILATION_CAPABLE_NODE_TYPES,
    ),
    DucoSensorEntityDescription(
        key="target_flow_level",
        translation_key="target_flow_level",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        suggested_display_precision=0,
        value_fn=lambda node: (
            node.ventilation.flow_lvl_tgt if node.ventilation else None
        ),
        node_types=VENTILATION_CAPABLE_NODE_TYPES,
    ),
    DucoSensorEntityDescription(
        key="time_state_end",
        translation_key="time_state_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda node: (
            dt_util.utc_from_timestamp(node.ventilation.time_state_end)
            if node.ventilation and node.ventilation.time_state_end != 0
            else None
        ),
        node_types=VENTILATION_CAPABLE_NODE_TYPES,
    ),
    DucoSensorEntityDescription(
        key="co2",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        value_fn=lambda node: node.sensor.co2 if node.sensor else None,
        node_types=(
            NodeType.BSCO2,
            NodeType.UCCO2,
            NodeType.VLVCO2,
            NodeType.VLVCO2RH,
        ),
    ),
    DucoSensorEntityDescription(
        key="iaq_co2",
        translation_key="iaq_co2",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda node: node.sensor.iaq_co2 if node.sensor else None,
        node_types=(
            NodeType.BSCO2,
            NodeType.UCCO2,
            NodeType.VLVCO2,
            NodeType.VLVCO2RH,
        ),
    ),
    DucoSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        value_fn=lambda node: node.sensor.rh if node.sensor else None,
        node_types=(NodeType.BSRH, NodeType.UCRH, NodeType.VLVRH, NodeType.VLVCO2RH),
    ),
    DucoSensorEntityDescription(
        key="iaq_rh",
        translation_key="iaq_rh",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda node: node.sensor.iaq_rh if node.sensor else None,
        node_types=(NodeType.BSRH, NodeType.UCRH, NodeType.VLVRH, NodeType.VLVCO2RH),
    ),
)

BOX_SENSOR_DESCRIPTIONS: tuple[DucoBoxSensorEntityDescription, ...] = (
    DucoBoxSensorEntityDescription(
        key="filter_remaining",
        translation_key="filter_remaining",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        suggested_display_precision=0,
        supported_fn=lambda coordinator: (
            coordinator.data.time_filter_remain is not None
        ),
        value_fn=lambda coordinator: coordinator.data.time_filter_remain,
    ),
    DucoBoxSensorEntityDescription(
        key="rssi_wifi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda coordinator: coordinator.data.rssi_wifi,
    ),
    DucoBoxSensorEntityDescription(
        key="outdoor_air_temperature",
        translation_key="outdoor_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        supported_fn=lambda coordinator: (
            coordinator.data.ventilation_temperatures is not None
            and coordinator.data.ventilation_temperatures.temp_oda is not None
        ),
        value_fn=lambda coordinator: (
            coordinator.data.ventilation_temperatures.temp_oda
            if coordinator.data.ventilation_temperatures
            else None
        ),
    ),
    DucoBoxSensorEntityDescription(
        key="supply_air_temperature",
        translation_key="supply_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        supported_fn=lambda coordinator: (
            coordinator.data.ventilation_temperatures is not None
            and coordinator.data.ventilation_temperatures.temp_sup is not None
        ),
        value_fn=lambda coordinator: (
            coordinator.data.ventilation_temperatures.temp_sup
            if coordinator.data.ventilation_temperatures
            else None
        ),
    ),
    DucoBoxSensorEntityDescription(
        key="extract_air_temperature",
        translation_key="extract_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        supported_fn=lambda coordinator: (
            coordinator.data.ventilation_temperatures is not None
            and coordinator.data.ventilation_temperatures.temp_eta is not None
        ),
        value_fn=lambda coordinator: (
            coordinator.data.ventilation_temperatures.temp_eta
            if coordinator.data.ventilation_temperatures
            else None
        ),
    ),
    DucoBoxSensorEntityDescription(
        key="exhaust_air_temperature",
        translation_key="exhaust_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        supported_fn=lambda coordinator: (
            coordinator.data.ventilation_temperatures is not None
            and coordinator.data.ventilation_temperatures.temp_eha is not None
        ),
        value_fn=lambda coordinator: (
            coordinator.data.ventilation_temperatures.temp_eha
            if coordinator.data.ventilation_temperatures
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DucoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Duco sensor entities."""
    coordinator = entry.runtime_data

    # Track the node IDs for which node entities have already been created, so
    # we can detect both newly added and stale (deregistered) nodes on every
    # coordinator update.
    known_nodes: set[int] = set()
    # Track optional box-level sensors separately so they can still be added
    # later if their capability probe transiently failed during initial setup.
    known_box_sensors: set[tuple[int, str]] = set()

    @callback
    def _async_add_new_entities() -> None:
        """Add new sensor entities and remove stale ones on coordinator updates."""
        # Remove devices whose nodes have disappeared from the API.
        # The firmware removes deregistered RF/wired nodes automatically.
        # BSRH box sensors that are physically unplugged from the PCB are
        # not deregistered by the firmware and will never appear here as stale.
        # The BOX node can transiently disappear from the API response, so keep
        # node 1 to avoid removing the main controller device.
        stale_node_ids = {
            node_id
            for node_id in known_nodes - coordinator.data.nodes.keys()
            if node_id != BOX_NODE_ID
        }
        if stale_node_ids:
            device_reg = dr.async_get(hass)
            mac = entry.unique_id
            for node_id in stale_node_ids:
                device = device_reg.async_get_device_by_identifier(
                    (DOMAIN, f"{mac}_{node_id}"), entry.entry_id
                )
                if device:
                    device_reg.async_update_device(
                        device.id,
                        remove_config_entry_id=entry.entry_id,
                    )
            known_nodes.difference_update(stale_node_ids)
            known_box_sensors.difference_update(
                {
                    description_key
                    for description_key in known_box_sensors
                    if description_key[0] in stale_node_ids
                }
            )

        new_entities: list[SensorEntity] = []
        for node in coordinator.data.nodes.values():
            if node.node_id not in known_nodes:
                if node.general.node_type == NodeType.UNKNOWN:
                    # Do not add the node to known_nodes so that it is re-evaluated
                    # on every coordinator update. This allows entities to be
                    # created automatically once a firmware update or library
                    # update adds support for the device type.
                    _LOGGER.debug(
                        "Duco node %s (%s) has an unsupported device type and will be "
                        "retried on subsequent coordinator updates",
                        node.node_id,
                        node.general.name,
                    )
                    continue
                known_nodes.add(node.node_id)
                new_entities.extend(
                    DucoSensorEntity(coordinator, node, description)
                    for description in SENSOR_DESCRIPTIONS
                    if node.general.node_type in description.node_types
                )

            if node.general.node_type != NodeType.BOX:
                continue

            for description in BOX_SENSOR_DESCRIPTIONS:
                description_key = (node.node_id, description.key)
                if description_key in known_box_sensors:
                    continue
                if not description.supported_fn(coordinator):
                    continue
                known_box_sensors.add(description_key)
                new_entities.append(DucoBoxSensorEntity(coordinator, node, description))
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
    @override
    def native_value(self) -> datetime | int | float | str | None:
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
    @override
    def native_value(self) -> int | float | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator)
