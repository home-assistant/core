"""Sensors and factory for enumerating devices from the Combined Energy API."""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Generator, Sequence
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

from .const import DATA_API_CLIENT, DATA_INSTALLATION, DATA_LOG_SESSION, DOMAIN
from .coordinator import (
    CombinedEnergyLogSessionService,
    CombinedEnergyReadingsDataService,
)

# Common sensors for all consumer devices
SENSOR_DESCRIPTIONS_GENERIC_CONSUMER = [
    SensorEntityDescription(
        key="energy_consumed",
        name="Energy Consumption",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SensorEntityDescription(
        key="power_consumption",
        name="Power Consumption",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    SensorEntityDescription(
        key="energy_consumed_solar",
        name="Energy Consumption Solar",
        icon="mdi:solar-power",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="power_consumption_solar",
        name="Power Consumption Solar",
        icon="mdi:solar-power",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="energy_consumed_battery",
        name="Energy Consumption Battery",
        icon="mdi:home-battery",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="power_consumption_battery",
        name="Power Consumption Battery",
        icon="mdi:home-battery",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="energy_consumed_grid",
        name="Energy Consumption Grid",
        icon="mdi:transmission-tower",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="power_consumption_grid",
        name="Power Consumption Grid",
        icon="mdi:transmission-tower",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
    ),
]
SENSOR_DESCRIPTIONS = {
    "SOLAR_PV": [
        SensorEntityDescription(
            key="energy_supplied",
            name="Energy Supplied",
            icon="mdi:solar-power",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
        ),
        SensorEntityDescription(
            key="power_supply",
            name="Power Supplied",
            icon="mdi:solar-power",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            device_class=SensorDeviceClass.POWER,
        ),
    ],
    "WATER_HEATER": (
        SENSOR_DESCRIPTIONS_GENERIC_CONSUMER
        + [
            SensorEntityDescription(
                key="available_energy",
                name="Hot Water Available",
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfVolume.LITERS,
                device_class=SensorDeviceClass.WATER,
            ),
            SensorEntityDescription(
                key="max_energy",
                name="Hot Water Max",
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfVolume.LITERS,
                device_class=SensorDeviceClass.WATER,
            ),
            SensorEntityDescription(
                key="output_temp",
                name="Output temperature",
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
            ),
            SensorEntityDescription(
                key="temp_sensor1",
                name="Temp Sensor 1",
                icon="mdi:thermometer-water",
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
                entity_registry_enabled_default=False,
            ),
            SensorEntityDescription(
                key="temp_sensor2",
                name="Water Temp 2",
                icon="mdi:thermometer-water",
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
                entity_registry_enabled_default=False,
            ),
            SensorEntityDescription(
                key="temp_sensor3",
                name="Water Temp 3",
                icon="mdi:thermometer-water",
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
                entity_registry_enabled_default=False,
            ),
            SensorEntityDescription(
                key="temp_sensor4",
                name="Water Temp 4",
                icon="mdi:thermometer-water",
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
                entity_registry_enabled_default=False,
            ),
            SensorEntityDescription(
                key="temp_sensor5",
                name="Water Temp 5",
                icon="mdi:thermometer-water",
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
                entity_registry_enabled_default=False,
            ),
            SensorEntityDescription(
                key="temp_sensor6",
                name="Water Temp 6",
                icon="mdi:thermometer-water",
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
                entity_registry_enabled_default=False,
            ),
        ]
    ),
    "GRID_METER": [
        SensorEntityDescription(
            key="energy_supplied",
            name="Energy Import",
            icon="mdi:transmission-tower",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
        ),
        SensorEntityDescription(
            key="power_supply",
            name="Power Import",
            icon="mdi:transmission-tower",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            device_class=SensorDeviceClass.POWER,
        ),
        SensorEntityDescription(
            key="energy_consumed",
            name="Energy Export",
            icon="mdi:transmission-tower",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
        ),
        SensorEntityDescription(
            key="power_consumption",
            name="Power Export",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            device_class=SensorDeviceClass.POWER,
        ),
        SensorEntityDescription(
            key="energy_consumed_solar",
            name="Energy Export Solar",
            icon="mdi:transmission-tower",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="power_consumption_solar",
            name="Power Export Solar",
            icon="mdi:solar-power",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            device_class=SensorDeviceClass.POWER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="energy_consumed_battery",
            name="Energy Export Battery",
            icon="mdi:transmission-tower",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="power_consumption_battery",
            name="Power Export Battery",
            icon="mdi:home-battery",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            device_class=SensorDeviceClass.POWER,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="power_factor_a",
            name="Power Factor A",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="%",
            device_class=SensorDeviceClass.POWER_FACTOR,
        ),
        SensorEntityDescription(
            key="power_factor_b",
            name="Power Factor B",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="%",
            device_class=SensorDeviceClass.POWER_FACTOR,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="power_factor_c",
            name="Power Factor C",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="%",
            device_class=SensorDeviceClass.POWER_FACTOR,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="voltage_a",
            name="Voltage A",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="V",
            device_class=SensorDeviceClass.VOLTAGE,
        ),
        SensorEntityDescription(
            key="voltage_b",
            name="Voltage B",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="V",
            device_class=SensorDeviceClass.VOLTAGE,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="voltage_c",
            name="Voltage C",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="V",
            device_class=SensorDeviceClass.VOLTAGE,
            entity_registry_enabled_default=False,
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

    # Initialise services
    log_session = CombinedEnergyLogSessionService(hass, api)
    log_session.async_setup()
    await log_session.coordinator.async_refresh()

    readings = CombinedEnergyReadingsDataService(hass, api)
    readings.async_setup()
    await readings.coordinator.async_refresh()

    # Store log session into Data
    hass.data[DOMAIN][entry.entry_id][DATA_LOG_SESSION] = log_session

    # Build entity list
    sensor_factory = CombinedEnergyReadingsSensorFactory(hass, installation, readings)
    entities: list[CombinedEnergyReadingsSensor] = list(sensor_factory.entities())
    async_add_entities(entities)


class CombinedEnergyReadingsSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Combined Energy API reading energy sensor."""

    data_service: CombinedEnergyReadingsDataService
    entity_description: SensorEntityDescription

    native_value_rounding: int = 2

    def __init__(
        self,
        device: Device,
        device_info: DeviceInfo,
        description: SensorEntityDescription,
        data_service: CombinedEnergyReadingsDataService,
    ) -> None:
        """Initialise Readings Sensor."""
        super().__init__(data_service.coordinator)

        self.device_id = device.device_id
        self.data_service = data_service
        self.entity_description = description

        self._attr_name = f"{device.display_name} {description.name}"
        self._attr_device_info = device_info
        self._attr_unique_id = (
            f"install_{self.data_service.api.installation_id}-"
            f"device_{device.device_id}-"
            f"{description.key}"
        )

    @property
    def device_readings(self) -> DeviceReadings | None:
        """Get readings for specific device."""
        if data := self.data_service.data:
            return data.get(self.device_id, None)
        return None

    @property
    def _raw_value(self) -> Any:
        """Get raw reading value from device readings."""
        if device_readings := self.device_readings:
            return getattr(device_readings, self.entity_description.key)
        return None

    @property
    def available(self) -> bool:
        """Indicate if the entity is available."""
        return self._raw_value is not None

    @abstractmethod
    def _to_native_value(self, raw_value: Any) -> int | float | None:
        """Convert non-none raw value into usable sensor value."""

    @property
    def native_value(self) -> int | float | None:
        """Return the state of the sensor."""
        if (raw_value := self._raw_value) is not None:
            return self._to_native_value(raw_value)
        return None


class GenericSensor(CombinedEnergyReadingsSensor):
    """Sensor that returns the last value of a sequence of readings."""

    def _to_native_value(self, raw_value: Any) -> float:
        """Convert non-none raw value into usable sensor value."""
        if isinstance(raw_value, Sequence):
            raw_value = raw_value[-1]
        return float(round(raw_value, self.native_value_rounding))


class EnergySensor(CombinedEnergyReadingsSensor):
    """Sensor for energy readings."""

    @property
    def last_reset(self) -> datetime | None:
        """Last time the data was reset."""
        if device_readings := self.device_readings:
            # mypy is struggling with a Pydantic model here, the cast isn't technically required
            return cast(datetime | None, device_readings.range_start)
        return None

    def _to_native_value(self, raw_value: Any) -> float:
        """Convert non-none raw value into usable sensor value."""
        value = sum(raw_value)
        return float(round(value, self.native_value_rounding))


class PowerSensor(CombinedEnergyReadingsSensor):
    """Sensor for power readings."""

    def _to_native_value(self, raw_value: Any) -> float:
        """Convert non-none raw value into usable sensor value."""
        return float(round(raw_value, self.native_value_rounding))


class PowerFactorSensor(CombinedEnergyReadingsSensor):
    """Sensor for power factor readings."""

    native_value_rounding = 1

    def _to_native_value(self, raw_value: Any) -> float:
        """Convert non-none raw value into usable sensor value."""
        # The API expresses the power factor as a fraction convert to %
        return float(round(raw_value[-1] * 100, self.native_value_rounding))


class WaterVolumeSensor(CombinedEnergyReadingsSensor):
    """Sensor for water volume readings."""

    def _to_native_value(self, raw_value: Any) -> int:
        """Convert non-none raw value into usable sensor value."""
        return int(round(raw_value[-1], 0))


# Map of common device classes to specific sensor types
SENSOR_TYPE_MAP: dict[
    SensorDeviceClass | str | None, type[CombinedEnergyReadingsSensor]
] = {
    SensorDeviceClass.ENERGY: EnergySensor,
    SensorDeviceClass.POWER: PowerSensor,
    SensorDeviceClass.WATER: WaterVolumeSensor,
    SensorDeviceClass.POWER_FACTOR: PowerFactorSensor,
    None: GenericSensor,
}


class CombinedEnergyReadingsSensorFactory:
    """Factory for generating devices/entities.

    Entities/Devices are described in the installation model.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        installation: Installation,
        readings: CombinedEnergyReadingsDataService,
    ) -> None:
        """Initialise readings sensor factory."""
        self.hass = hass
        self.installation = installation
        self.readings = readings

    def _generate_device_info(self, device: Device) -> DeviceInfo:
        """Generate device info from API device response."""
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"install_{self.installation.installation_id}-device_{device.device_id}",
                )
            },
            manufacturer=device.device_manufacturer,
            model=device.device_model_name,
            name=device.display_name,
        )

    def entities(self) -> Generator[CombinedEnergyReadingsSensor, None, None]:
        """Generate entities."""

        for device in self.installation.devices:
            if descriptions := SENSOR_DESCRIPTIONS.get(device.device_type):
                device_info = self._generate_device_info(device)

                # Generate sensors from descriptions for the current device type
                for description in descriptions:
                    if sensor_type := SENSOR_TYPE_MAP.get(
                        description.device_class, GenericSensor
                    ):
                        yield sensor_type(
                            device,
                            device_info,
                            description,
                            self.readings,
                        )
