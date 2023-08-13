"""Discovergy sensor entity."""
from dataclasses import dataclass, field

from pydiscovergy.models import Meter

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DiscovergyData, DiscovergyUpdateCoordinator
from .const import DOMAIN, MANUFACTURER

PARALLEL_UPDATES = 1


@dataclass
class DiscovergyMixin:
    """Mixin for alternative keys."""

    alternative_keys: list[str] = field(default_factory=lambda: [])
    scale: int = field(default_factory=lambda: 1000)


@dataclass
class DiscovergySensorEntityDescription(DiscovergyMixin, SensorEntityDescription):
    """Define Sensor entity description class."""


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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Discovergy sensors."""
    data: DiscovergyData = hass.data[DOMAIN][entry.entry_id]
    meters: list[Meter] = data.meters  # always returns a list

    entities: list[DiscovergySensor] = []
    for meter in meters:
        sensors = None
        if meter.measurement_type == "ELECTRICITY":
            sensors = ELECTRICITY_SENSORS
        elif meter.measurement_type == "GAS":
            sensors = GAS_SENSORS

        if sensors is not None:
            for description in sensors:
                # check if this meter has this data, then add this sensor
                for key in {description.key, *description.alternative_keys}:
                    coordinator: DiscovergyUpdateCoordinator = data.coordinators[
                        meter.meter_id
                    ]
                    if key in coordinator.data.values:
                        entities.append(
                            DiscovergySensor(key, description, meter, coordinator)
                        )

    async_add_entities(entities, False)


class DiscovergySensor(CoordinatorEntity[DiscovergyUpdateCoordinator], SensorEntity):
    """Represents a discovergy smart meter sensor."""

    entity_description: DiscovergySensorEntityDescription
    data_key: str
    _attr_has_entity_name = True

    def __init__(
        self,
        data_key: str,
        description: DiscovergySensorEntityDescription,
        meter: Meter,
        coordinator: DiscovergyUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.data_key = data_key

        self.entity_description = description
        self._attr_unique_id = f"{meter.full_serial_number}-{data_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, meter.meter_id)},
            name=f"{meter.measurement_type.capitalize()} {meter.location.street} {meter.location.street_number}",
            model=f"{meter.type} {meter.full_serial_number}",
            manufacturer=MANUFACTURER,
        )

    @property
    def native_value(self) -> StateType:
        """Return the sensor state."""
        return float(
            self.coordinator.data.values[self.data_key] / self.entity_description.scale
        )
