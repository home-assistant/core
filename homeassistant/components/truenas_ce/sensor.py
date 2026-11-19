"""Sensor platform for the TrueNAS integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfRatio,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import TrueNASConfigEntry, TrueNASCoordinator, TrueNASData
from .entity import TrueNASEntity

# Updates are centralized in the coordinator.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TrueNASSensorEntityDescription(SensorEntityDescription):
    """Describes a TrueNAS sensor.

    ``value_fn`` gets the coordinator data and the network interface id of
    the entity (``None`` for a system sensor).
    """

    value_fn: Callable[[TrueNASData, str | None], StateType | datetime]
    exists_fn: Callable[[TrueNASData], bool] = lambda _: True


def _rx_kbps(data: TrueNASData, interface_id: str | None) -> float | None:
    """Return the receive rate of an interface."""
    traffic = data.stats.interfaces.get(interface_id) if interface_id else None
    return traffic.rx_kbps if traffic else None


def _tx_kbps(data: TrueNASData, interface_id: str | None) -> float | None:
    """Return the transmit rate of an interface."""
    traffic = data.stats.interfaces.get(interface_id) if interface_id else None
    return traffic.tx_kbps if traffic else None


SYSTEM_SENSORS: tuple[TrueNASSensorEntityDescription, ...] = (
    TrueNASSensorEntityDescription(
        key="system_uptime",
        translation_key="system_uptime",
        device_class=SensorDeviceClass.UPTIME,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data, _: data.info.boot_time,
    ),
    TrueNASSensorEntityDescription(
        key="system_cpu_temperature",
        translation_key="system_cpu_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data, _: data.stats.cpu_temperature,
        # None on a virtual machine and on hardware without a sensor.
        exists_fn=lambda data: data.stats.cpu_temperature is not None,
    ),
    TrueNASSensorEntityDescription(
        key="system_load_shortterm",
        translation_key="system_load_shortterm",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data, _: data.info.load_1m,
    ),
    TrueNASSensorEntityDescription(
        key="system_load_midterm",
        translation_key="system_load_midterm",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data, _: data.info.load_5m,
    ),
    TrueNASSensorEntityDescription(
        key="system_load_longterm",
        translation_key="system_load_longterm",
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data, _: data.info.load_15m,
    ),
    TrueNASSensorEntityDescription(
        key="system_cpu_usage",
        translation_key="system_cpu_usage",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data, _: data.stats.cpu_usage_percent,
    ),
    TrueNASSensorEntityDescription(
        key="system_memory_usage",
        translation_key="system_memory_usage",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data, _: data.stats.memory_usage_percent,
    ),
    TrueNASSensorEntityDescription(
        key="system_cache_size-arc_value",
        translation_key="system_cache_size_arc_value",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data, _: data.stats.arc_size,
    ),
    TrueNASSensorEntityDescription(
        key="system_memory_total",
        translation_key="system_memory_total",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data, _: data.info.physical_memory,
    ),
    TrueNASSensorEntityDescription(
        key="system_memory_free",
        translation_key="system_memory_free",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data, _: data.stats.memory_available,
    ),
)

INTERFACE_SENSORS: tuple[TrueNASSensorEntityDescription, ...] = (
    TrueNASSensorEntityDescription(
        key="traffic_rx",
        translation_key="traffic_rx",
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_rx_kbps,
    ),
    TrueNASSensorEntityDescription(
        key="traffic_tx",
        translation_key="traffic_tx",
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_tx_kbps,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrueNASConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TrueNAS sensors."""
    coordinator = entry.runtime_data
    known_system_sensors: set[str] = set()
    known_interfaces: set[str] = set()

    @callback
    def _async_add_new_sensors() -> None:
        """Add system sensors whose data appeared and traffic sensors for new links.

        A traffic sensor is added for an interface that is new or whose link
        came up, a system sensor once its data exists (e.g. a temperature).
        """
        new_descriptions = [
            description
            for description in SYSTEM_SENSORS
            if description.key not in known_system_sensors
            and description.exists_fn(coordinator.data)
        ]
        known_system_sensors.update(description.key for description in new_descriptions)
        new_interfaces = {
            interface_id
            for interface_id, interface in coordinator.data.interfaces.items()
            if interface.link_up is not False
        } - known_interfaces
        known_interfaces.update(new_interfaces)

        entities = [
            TrueNASSensor(coordinator, description) for description in new_descriptions
        ]
        entities.extend(
            TrueNASSensor(coordinator, description, interface_id)
            for interface_id in sorted(new_interfaces)
            for description in INTERFACE_SENSORS
        )
        if entities:
            async_add_entities(entities)

    _async_add_new_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_sensors))


class TrueNASSensor(TrueNASEntity, SensorEntity):
    """Representation of a TrueNAS sensor."""

    entity_description: TrueNASSensorEntityDescription

    def __init__(
        self,
        coordinator: TrueNASCoordinator,
        description: TrueNASSensorEntityDescription,
        interface_id: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._interface_id = interface_id
        unique_id = f"{coordinator.system_id.lower()}-{description.key}"
        if interface_id is not None:
            unique_id = f"{unique_id}-{interface_id}"
            interface = coordinator.data.interfaces[interface_id]
            self._attr_translation_placeholders = {
                "interface": interface.name or interface_id
            }
        self._attr_unique_id = unique_id

    @property
    @override
    def available(self) -> bool:
        """Return whether the sensor's interface is still reported."""
        return super().available and (
            self._interface_id is None
            or self._interface_id in self.coordinator.data.interfaces
        )

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(
            self.coordinator.data, self._interface_id
        )
