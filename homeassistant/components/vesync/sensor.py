"""Support for voltage, power & energy sensors for VeSync outlets."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from pyvesync.base_devices.vesyncbasedevice import VeSyncBaseDevice
from pyvesync.device_container import DeviceContainer

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .common import is_air_fryer, is_humidifier, is_outlet, rgetattr
from .const import AIR_FRYER_MODE_MAP, VS_DEVICES, VS_DISCOVERY
from .coordinator import VesyncConfigEntry, VeSyncDataCoordinator
from .entity import VeSyncBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class VeSyncSensorEntityDescription(SensorEntityDescription):
    """Describe VeSync sensor entity."""

    value_fn: Callable[[VeSyncBaseDevice], StateType]

    exists_fn: Callable[[VeSyncBaseDevice], bool]

    use_device_temperature_unit: bool = False


SENSORS: tuple[VeSyncSensorEntityDescription, ...] = (
    VeSyncSensorEntityDescription(
        key="filter-life",
        translation_key="filter_life",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.state.filter_life,
        exists_fn=lambda device: rgetattr(device, "state.filter_life") is not None,
    ),
    VeSyncSensorEntityDescription(
        key="air-quality",
        translation_key="air_quality",
        value_fn=lambda device: device.state.air_quality_string,
        exists_fn=(
            lambda device: rgetattr(device, "state.air_quality_string") is not None
        ),
    ),
    VeSyncSensorEntityDescription(
        key="pm1",
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.state.pm1,
        exists_fn=lambda device: rgetattr(device, "state.pm1") is not None,
    ),
    VeSyncSensorEntityDescription(
        key="pm10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.state.pm10,
        exists_fn=lambda device: rgetattr(device, "state.pm10") is not None,
    ),
    VeSyncSensorEntityDescription(
        key="pm25",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.state.pm25,
        exists_fn=lambda device: rgetattr(device, "state.pm25") is not None,
    ),
    VeSyncSensorEntityDescription(
        key="power",
        translation_key="current_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.state.power,
        exists_fn=is_outlet,
    ),
    VeSyncSensorEntityDescription(
        key="energy",
        translation_key="energy_today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device: device.state.energy,
        exists_fn=is_outlet,
    ),
    VeSyncSensorEntityDescription(
        key="energy-weekly",
        translation_key="energy_week",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device: getattr(
            device.state.weekly_history, "totalEnergy", None
        ),
        exists_fn=is_outlet,
    ),
    VeSyncSensorEntityDescription(
        key="energy-monthly",
        translation_key="energy_month",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device: getattr(
            device.state.monthly_history, "totalEnergy", None
        ),
        exists_fn=is_outlet,
    ),
    VeSyncSensorEntityDescription(
        key="energy-yearly",
        translation_key="energy_year",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device: getattr(
            device.state.yearly_history, "totalEnergy", None
        ),
        exists_fn=is_outlet,
    ),
    VeSyncSensorEntityDescription(
        key="voltage",
        translation_key="current_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.state.voltage,
        exists_fn=is_outlet,
    ),
    VeSyncSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.state.humidity,
        exists_fn=is_humidifier,
    ),
    VeSyncSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.state.temperature,
        exists_fn=lambda device: (
            is_humidifier(device) and device.state.temperature is not None
        ),
    ),
    VeSyncSensorEntityDescription(
        key="cook_status",
        translation_key="cook_status",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda device: AIR_FRYER_MODE_MAP.get(
            device.state.cook_status.lower(), device.state.cook_status.lower()
        ),
        exists_fn=is_air_fryer,
        options=[
            "cooking_end",
            "cooking",
            "cooking_stop",
            "heating",
            "preheat_end",
            "preheat_stop",
            "pull_out",
            "standby",
        ],
    ),
    VeSyncSensorEntityDescription(
        key="current_temp",
        translation_key="current_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        use_device_temperature_unit=True,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.state.current_temp,
        exists_fn=is_air_fryer,
    ),
    VeSyncSensorEntityDescription(
        key="cook_set_temp",
        translation_key="cook_set_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        use_device_temperature_unit=True,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.state.cook_set_temp,
        exists_fn=is_air_fryer,
    ),
    VeSyncSensorEntityDescription(
        key="cook_set_time",
        translation_key="cook_set_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda device: device.state.cook_set_time,
        exists_fn=is_air_fryer,
    ),
    VeSyncSensorEntityDescription(
        key="preheat_set_time",
        translation_key="preheat_set_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda device: device.state.preheat_set_time,
        exists_fn=is_air_fryer,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VesyncConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switches."""

    coordinator = config_entry.runtime_data

    @callback
    def discover(devices: list[VeSyncBaseDevice]) -> None:
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities, coordinator)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_DEVICES), discover)
    )

    _setup_entities(
        config_entry.runtime_data.manager.devices, async_add_entities, coordinator
    )


@callback
def _setup_entities(
    devices: DeviceContainer | list[VeSyncBaseDevice],
    async_add_entities: AddConfigEntryEntitiesCallback,
    coordinator: VeSyncDataCoordinator,
) -> None:
    """Check if device is online and add entity."""

    async_add_entities(
        (
            VeSyncSensorEntity(dev, description, coordinator)
            for dev in devices
            for description in SENSORS
            if description.exists_fn(dev)
        ),
        update_before_add=True,
    )


class VeSyncSensorEntity(VeSyncBaseEntity, SensorEntity):
    """Representation of a sensor describing a VeSync device."""

    entity_description: VeSyncSensorEntityDescription

    def __init__(
        self,
        device: VeSyncBaseDevice,
        description: VeSyncSensorEntityDescription,
        coordinator: VeSyncDataCoordinator,
    ) -> None:
        """Initialize the VeSync outlet device."""
        super().__init__(device, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}-{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.device)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit the value was reported in by the sensor."""
        if self.entity_description.use_device_temperature_unit:
            if self.device.temp_unit == "celsius":
                return UnitOfTemperature.CELSIUS
            if self.device.temp_unit == "fahrenheit":
                return UnitOfTemperature.FAHRENHEIT
        return super().native_unit_of_measurement
