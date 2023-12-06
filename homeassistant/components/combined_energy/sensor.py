"""Sensors and factory for enumerating devices from the Combined Energy API."""
from __future__ import annotations

from collections.abc import Callable, Generator, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from combined_energy import CombinedEnergy
from combined_energy.models import Device, DeviceReadings, Installation

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_API_CLIENT, DATA_INSTALLATION, DOMAIN
from .coordinator import CombinedEnergyReadingsCoordinator


def _generic_native_value(
    raw_value: float | list[float], precision: int | None
) -> float:
    """Convert last measured value into a float."""
    if isinstance(raw_value, Sequence):
        raw_value = raw_value[-1]
    return float(round(raw_value, precision))


def _energy_native_value(raw_value: list[float], precision: int | None) -> float:
    """Sum all values into a total value for the measurement range."""
    value = sum(raw_value)
    return float(round(value, precision))


def _power_factor_native_value(raw_value: list[float], precision: int | None) -> float:
    """Convert last measured power factor is expressed as a fraction into a %."""
    return float(round(raw_value[-1] * 100, precision))


def _water_volume_native_value(raw_value: list[float], precision: int | None) -> int:
    """Convert last measured water volume into an integer."""
    return int(round(raw_value[-1], precision))


@dataclass(kw_only=True)
class CombinedEnergySensorEntityDescription(SensorEntityDescription):
    """Class describing combined energy sensor entity."""

    native_value_fn: Callable[[Any, int | None], float | int]


# Common sensors for all consumer devices
SENSOR_DESCRIPTIONS_GENERIC_CONSUMER = [
    CombinedEnergySensorEntityDescription(
        key="energy_consumed",
        translation_key="energy_consumed",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=2,
        native_value_fn=_energy_native_value,
    ),
    CombinedEnergySensorEntityDescription(
        key="power_consumption",
        translation_key="power_consumption",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        suggested_display_precision=2,
        native_value_fn=_generic_native_value,
    ),
    CombinedEnergySensorEntityDescription(
        key="energy_consumed_solar",
        translation_key="energy_consumed_solar",
        icon="mdi:solar-power",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        native_value_fn=_generic_native_value,
    ),
    CombinedEnergySensorEntityDescription(
        key="power_consumption_solar",
        translation_key="power_consumption_solar",
        icon="mdi:solar-power",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        native_value_fn=_generic_native_value,
    ),
    CombinedEnergySensorEntityDescription(
        key="energy_consumed_battery",
        translation_key="energy_consumed_battery",
        icon="mdi:home-battery",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        native_value_fn=_energy_native_value,
    ),
    CombinedEnergySensorEntityDescription(
        key="power_consumption_battery",
        translation_key="power_consumption_battery",
        icon="mdi:home-battery",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        native_value_fn=_generic_native_value,
    ),
    CombinedEnergySensorEntityDescription(
        key="energy_consumed_grid",
        translation_key="energy_consumed_grid",
        icon="mdi:transmission-tower",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        native_value_fn=_generic_native_value,
    ),
    CombinedEnergySensorEntityDescription(
        key="power_consumption_grid",
        translation_key="power_consumption_grid",
        icon="mdi:transmission-tower",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        native_value_fn=_generic_native_value,
    ),
]
SENSOR_DESCRIPTIONS = {
    "SOLAR_PV": [
        CombinedEnergySensorEntityDescription(
            key="energy_supplied",
            translation_key="solar_pv_energy_supplied",
            icon="mdi:solar-power",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            suggested_display_precision=2,
            native_value_fn=_generic_native_value,
        ),
        CombinedEnergySensorEntityDescription(
            key="power_supply",
            translation_key="solar_pv_power_supply",
            icon="mdi:solar-power",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            device_class=SensorDeviceClass.POWER,
            suggested_display_precision=2,
            native_value_fn=_generic_native_value,
        ),
    ],
    "WATER_HEATER": (
        SENSOR_DESCRIPTIONS_GENERIC_CONSUMER
        + [
            CombinedEnergySensorEntityDescription(
                key="available_energy",
                translation_key="water_heater_available_energy",
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfVolume.LITERS,
                device_class=SensorDeviceClass.WATER,
                suggested_display_precision=0,
                native_value_fn=_water_volume_native_value,
            ),
            CombinedEnergySensorEntityDescription(
                key="max_energy",
                translation_key="water_heater_max_energy",
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfVolume.LITERS,
                device_class=SensorDeviceClass.WATER,
                suggested_display_precision=0,
                native_value_fn=_water_volume_native_value,
            ),
            CombinedEnergySensorEntityDescription(
                key="output_temp",
                translation_key="water_heater_output_temp",
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
                suggested_display_precision=2,
                native_value_fn=_generic_native_value,
            ),
            CombinedEnergySensorEntityDescription(
                key="temp_sensor1",
                translation_key="water_heater_temp_sensor1",
                icon="mdi:thermometer-water",
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
                suggested_display_precision=2,
                entity_registry_enabled_default=False,
                native_value_fn=_generic_native_value,
            ),
            CombinedEnergySensorEntityDescription(
                key="temp_sensor2",
                translation_key="water_heater_temp_sensor2",
                icon="mdi:thermometer-water",
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
                suggested_display_precision=2,
                entity_registry_enabled_default=False,
                native_value_fn=_generic_native_value,
            ),
            CombinedEnergySensorEntityDescription(
                key="temp_sensor3",
                translation_key="water_heater_temp_sensor3",
                icon="mdi:thermometer-water",
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
                suggested_display_precision=2,
                entity_registry_enabled_default=False,
                native_value_fn=_generic_native_value,
            ),
            CombinedEnergySensorEntityDescription(
                key="temp_sensor4",
                translation_key="water_heater_temp_sensor4",
                icon="mdi:thermometer-water",
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
                suggested_display_precision=2,
                entity_registry_enabled_default=False,
                native_value_fn=_generic_native_value,
            ),
            CombinedEnergySensorEntityDescription(
                key="temp_sensor5",
                translation_key="water_heater_temp_sensor5",
                icon="mdi:thermometer-water",
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
                suggested_display_precision=2,
                entity_registry_enabled_default=False,
                native_value_fn=_generic_native_value,
            ),
            CombinedEnergySensorEntityDescription(
                key="temp_sensor6",
                translation_key="water_heater_temp_sensor6",
                icon="mdi:thermometer-water",
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
                suggested_display_precision=2,
                entity_registry_enabled_default=False,
                native_value_fn=_generic_native_value,
            ),
        ]
    ),
    "GRID_METER": [
        CombinedEnergySensorEntityDescription(
            key="energy_supplied",
            translation_key="grid_meter_energy_supplied",
            icon="mdi:transmission-tower",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            suggested_display_precision=2,
            native_value_fn=_generic_native_value,
        ),
        CombinedEnergySensorEntityDescription(
            key="power_supply",
            translation_key="grid_meter_power_supply",
            icon="mdi:transmission-tower",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            device_class=SensorDeviceClass.POWER,
            suggested_display_precision=2,
            native_value_fn=_generic_native_value,
        ),
        CombinedEnergySensorEntityDescription(
            key="energy_consumed",
            translation_key="grid_meter_energy_consumed",
            icon="mdi:transmission-tower",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            suggested_display_precision=2,
            native_value_fn=_generic_native_value,
        ),
        CombinedEnergySensorEntityDescription(
            key="power_consumption",
            translation_key="grid_meter_power_consumption",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            device_class=SensorDeviceClass.POWER,
            suggested_display_precision=2,
            native_value_fn=_generic_native_value,
        ),
        CombinedEnergySensorEntityDescription(
            key="energy_consumed_solar",
            translation_key="grid_meter_energy_consumed_solar",
            icon="mdi:transmission-tower",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            suggested_display_precision=2,
            entity_registry_enabled_default=False,
            native_value_fn=_generic_native_value,
        ),
        CombinedEnergySensorEntityDescription(
            key="power_consumption_solar",
            translation_key="grid_meter_power_consumption_solar",
            icon="mdi:solar-power",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            device_class=SensorDeviceClass.POWER,
            suggested_display_precision=2,
            entity_registry_enabled_default=False,
            native_value_fn=_generic_native_value,
        ),
        CombinedEnergySensorEntityDescription(
            key="energy_consumed_battery",
            translation_key="grid_meter_energy_consumed_battery",
            icon="mdi:transmission-tower",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            suggested_display_precision=2,
            entity_registry_enabled_default=False,
            native_value_fn=_generic_native_value,
        ),
        CombinedEnergySensorEntityDescription(
            key="power_consumption_battery",
            translation_key="grid_meter_power_consumption_battery",
            icon="mdi:home-battery",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            device_class=SensorDeviceClass.POWER,
            suggested_display_precision=2,
            entity_registry_enabled_default=False,
            native_value_fn=_generic_native_value,
        ),
        CombinedEnergySensorEntityDescription(
            key="power_factor_a",
            translation_key="grid_meter_power_factor_a",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="%",
            device_class=SensorDeviceClass.POWER_FACTOR,
            suggested_display_precision=1,
            native_value_fn=_power_factor_native_value,
        ),
        CombinedEnergySensorEntityDescription(
            key="power_factor_b",
            translation_key="grid_meter_power_factor_b",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="%",
            device_class=SensorDeviceClass.POWER_FACTOR,
            suggested_display_precision=1,
            entity_registry_enabled_default=False,
            native_value_fn=_power_factor_native_value,
        ),
        CombinedEnergySensorEntityDescription(
            key="power_factor_c",
            translation_key="grid_meter_power_factor_c",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="%",
            device_class=SensorDeviceClass.POWER_FACTOR,
            suggested_display_precision=1,
            entity_registry_enabled_default=False,
            native_value_fn=_power_factor_native_value,
        ),
        CombinedEnergySensorEntityDescription(
            key="voltage_a",
            translation_key="grid_meter_voltage_a",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="V",
            device_class=SensorDeviceClass.VOLTAGE,
            suggested_display_precision=2,
            native_value_fn=_generic_native_value,
        ),
        CombinedEnergySensorEntityDescription(
            key="voltage_b",
            translation_key="grid_meter_voltage_b",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="V",
            device_class=SensorDeviceClass.VOLTAGE,
            suggested_display_precision=2,
            entity_registry_enabled_default=False,
            native_value_fn=_generic_native_value,
        ),
        CombinedEnergySensorEntityDescription(
            key="voltage_c",
            translation_key="grid_meter_voltage_c",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="V",
            device_class=SensorDeviceClass.VOLTAGE,
            suggested_display_precision=2,
            entity_registry_enabled_default=False,
            native_value_fn=_generic_native_value,
        ),
    ],
    "GENERIC_CONSUMER": SENSOR_DESCRIPTIONS_GENERIC_CONSUMER,
    "ENERGY_BALANCE": SENSOR_DESCRIPTIONS_GENERIC_CONSUMER,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""

    api: CombinedEnergy = hass.data[DOMAIN][entry.entry_id][DATA_API_CLIENT]
    installation: Installation = hass.data[DOMAIN][entry.entry_id][DATA_INSTALLATION]

    # Initialise readings coordinator
    readings = CombinedEnergyReadingsCoordinator(hass, api)
    await readings.async_config_entry_first_refresh()

    async_add_entities(_generate_sensors(installation, readings))


def _generate_sensors(
    installation: Installation,
    readings: CombinedEnergyReadingsCoordinator,
) -> Generator[CombinedEnergyReadingsSensor, None, None]:
    """Generate sensor entities from installed devices."""

    for device in installation.devices:
        if descriptions := SENSOR_DESCRIPTIONS.get(device.device_type):
            # Generate sensors from descriptions for the current device type
            for description in descriptions:
                yield CombinedEnergyReadingsSensor(device, description, readings)


class CombinedEnergyReadingsSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Combined Energy API reading energy sensor."""

    entity_description: CombinedEnergySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        device: Device,
        description: CombinedEnergySensorEntityDescription,
        coordinator: CombinedEnergyReadingsCoordinator,
    ) -> None:
        """Initialise Readings Sensor."""
        super().__init__(coordinator)

        self.device_id = device.device_id
        self.entity_description = description

        identifier = f"{self.coordinator.api.installation_id}_{device.device_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            manufacturer=device.device_manufacturer,
            model=device.device_model_name,
            name=device.display_name,
        )
        self._attr_unique_id = f"{identifier}-{description.key}"

    @property
    def device_readings(self) -> DeviceReadings | None:
        """Get readings for specific device."""
        if data := self.coordinator.data:
            return data.get(self.device_id, None)
        return None

    @property
    def _raw_value(self) -> Any:
        """Get raw reading value from device readings."""
        if device_readings := self.device_readings:
            return getattr(device_readings, self.entity_description.key, None)
        return None

    @property
    def available(self) -> bool:
        """Indicate if the entity is available."""
        return super().available and self._raw_value is not None

    @property
    def native_value(self) -> int | float | None:
        """Return the state of the sensor."""
        if (raw_value := self._raw_value) is not None:
            return self.entity_description.native_value_fn(
                raw_value, self.suggested_display_precision
            )
        return None

    @property
    def last_reset(self) -> datetime | None:
        """Last time the data was reset."""
        if device_readings := self.device_readings:
            # mypy is struggling with a Pydantic model here, the cast isn't technically required
            return cast(datetime | None, device_readings.range_start)
        return None
