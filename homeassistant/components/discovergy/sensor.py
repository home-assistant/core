"""Discovergy sensor entity."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from pydiscovergy.models import Reading

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DiscovergyConfigEntry
from .const import DOMAIN, MANUFACTURER
from .coordinator import DiscovergyUpdateCoordinator


def _get_and_scale(reading: Reading, key: str, scale: int) -> datetime | float | None:
    """Get a value from a Reading and divide with scale it."""
    if (value := reading.values.get(key)) is not None:
        return value / scale
    return None


@dataclass(frozen=True, kw_only=True)
class DiscovergySensorEntityDescription(SensorEntityDescription):
    """Class to describe a Discovergy sensor entity."""

    value_fn: Callable[[Reading, str, int], datetime | float | None] = field(
        default=_get_and_scale
    )
    alternative_keys: list[str] = field(default_factory=list)
    scale: int = field(default_factory=lambda: 1000)


GAS_SENSORS: tuple[DiscovergySensorEntityDescription, ...] = (
    DiscovergySensorEntityDescription(
        key="volume",
        translation_key="total_gas_consumption",
        suggested_display_precision=4,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)

ELECTRICITY_SENSORS: tuple[DiscovergySensorEntityDescription, ...] = (
    # power sensors
    DiscovergySensorEntityDescription(
        key="power",
        translation_key="total_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=3,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DiscovergySensorEntityDescription(
        key="power1",
        translation_key="phase_1_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=3,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        alternative_keys=["phase1Power"],
    ),
    DiscovergySensorEntityDescription(
        key="power2",
        translation_key="phase_2_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=3,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        alternative_keys=["phase2Power"],
    ),
    DiscovergySensorEntityDescription(
        key="power3",
        translation_key="phase_3_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=3,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        alternative_keys=["phase3Power"],
    ),
    # voltage sensors
    DiscovergySensorEntityDescription(
        key="phase1Voltage",
        translation_key="phase_1_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        alternative_keys=["voltage1"],
    ),
    DiscovergySensorEntityDescription(
        key="phase2Voltage",
        translation_key="phase_2_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        alternative_keys=["voltage2"],
    ),
    DiscovergySensorEntityDescription(
        key="phase3Voltage",
        translation_key="phase_3_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        alternative_keys=["voltage3"],
    ),
    # energy sensors
    DiscovergySensorEntityDescription(
        key="energy",
        translation_key="total_consumption",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=4,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        scale=10000000000,
    ),
    DiscovergySensorEntityDescription(
        key="energyOut",
        translation_key="total_production",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=4,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        scale=10000000000,
    ),
)

ADDITIONAL_SENSORS: tuple[DiscovergySensorEntityDescription, ...] = (
    DiscovergySensorEntityDescription(
        key="last_transmitted",
        translation_key="last_transmitted",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda reading, key, scale: reading.time,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DiscovergyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Discovergy sensors."""
    entities: list[DiscovergySensor] = []
    for coordinator in entry.runtime_data:
        sensors: tuple[DiscovergySensorEntityDescription, ...] = ()

        # select sensor descriptions based on meter type and combine with additional sensors
        if coordinator.meter.measurement_type == "ELECTRICITY":
            sensors = ELECTRICITY_SENSORS + ADDITIONAL_SENSORS
        elif coordinator.meter.measurement_type == "GAS":
            sensors = GAS_SENSORS + ADDITIONAL_SENSORS

        entities.extend(
            DiscovergySensor(value_key, description, coordinator)
            for description in sensors
            for value_key in {description.key, *description.alternative_keys}
            if description.value_fn(coordinator.data, value_key, description.scale)
            is not None
        )

    async_add_entities(entities)


class DiscovergySensor(CoordinatorEntity[DiscovergyUpdateCoordinator], SensorEntity):
    """Represents a Discovergy smart meter sensor."""

    entity_description: DiscovergySensorEntityDescription
    data_key: str
    _attr_has_entity_name = True

    def __init__(
        self,
        data_key: str,
        description: DiscovergySensorEntityDescription,
        coordinator: DiscovergyUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.data_key = data_key
        self.entity_description = description

        meter = coordinator.meter
        self._attr_unique_id = f"{meter.full_serial_number}-{data_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, meter.meter_id)},
            name=f"{meter.measurement_type.capitalize()} {meter.location.street} {meter.location.street_number}",
            model=meter.meter_type,
            manufacturer=MANUFACTURER,
            serial_number=meter.full_serial_number,
        )

    @property
    def native_value(self) -> datetime | float | None:
        """Return the sensor state."""
        return self.entity_description.value_fn(
            self.coordinator.data, self.data_key, self.entity_description.scale
        )
