"""Constants for the Combined Energy integration."""
from datetime import timedelta
import logging
from typing import Final

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfVolume,
)

DOMAIN: Final[str] = "combined_energy"

LOGGER = logging.getLogger(__package__)

# Data for Combined Energy requests.
DATA_API_CLIENT: Final[str] = "api_client"
DATA_LOG_SESSION: Final[str] = "log_session"
DATA_INSTALLATION: Final[str] = "installation"

# Config for combined energy requests.
CONF_INSTALLATION_ID: Final[str] = "installation_id"
DEFAULT_NAME: Final[str] = "Combined Energy"

CONNECTIVITY_UPDATE_DELAY: Final[timedelta] = timedelta(seconds=30)
LOG_SESSION_REFRESH_DELAY: Final[timedelta] = timedelta(minutes=15)
READINGS_UPDATE_DELAY: Final[timedelta] = timedelta(minutes=1)

# Increment size in seconds; Valid values are 5/300/1800 (5s/5m/30m)
READINGS_INCREMENT: Final[int] = 5
READINGS_INITIAL_DELTA: Final[timedelta] = timedelta(seconds=40)

# Supported sensors
SENSOR_DESCRIPTION_CONNECTED = BinarySensorEntityDescription(
    key="connected",
    name="Monitor Connected",
    icon="mdi:wifi-cog",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
)
# Common sensors for all consumer devices
SENSOR_DESCRIPTIONS_GENERIC_CONSUMER = [
    SensorEntityDescription(
        key="energy_consumed",
        name="Energy Consumption",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SensorEntityDescription(
        key="energy_consumed_solar",
        name="Energy Consumption Solar",
        icon="mdi:solar-power",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SensorEntityDescription(
        key="energy_consumed_battery",
        name="Energy Consumption Battery",
        icon="mdi:home-battery",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="energy_consumed_grid",
        name="Energy Consumption Grid",
        icon="mdi:transmission-tower",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
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
        key="power_consumption_solar",
        name="Power Consumption Solar",
        icon="mdi:solar-power",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
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
        key="power_consumption_grid",
        name="Power Consumption Grid",
        icon="mdi:transmission-tower",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
]
SENSOR_DESCRIPTIONS = {
    "SOLAR_PV": [
        SensorEntityDescription(
            key="energy_supplied",
            name="Energy Supplied",
            icon="mdi:solar-power",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
        ),
        SensorEntityDescription(
            key="power_supply",
            name="Power Supply",
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
            ),
            SensorEntityDescription(
                key="temp_sensor2",
                name="Water Temp 2",
                icon="mdi:thermometer-water",
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
            ),
            SensorEntityDescription(
                key="temp_sensor3",
                name="Water Temp 3",
                icon="mdi:thermometer-water",
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
            ),
            SensorEntityDescription(
                key="temp_sensor4",
                name="Water Temp 4",
                icon="mdi:thermometer-water",
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
            ),
            SensorEntityDescription(
                key="temp_sensor5",
                name="Water Temp 5",
                icon="mdi:thermometer-water",
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
            ),
            SensorEntityDescription(
                key="temp_sensor6",
                name="Water Temp 6",
                icon="mdi:thermometer-water",
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
            ),
        ]
    ),
    "GRID_METER": [
        SensorEntityDescription(
            key="energy_supplied",
            name="Energy Import",
            icon="mdi:transmission-tower",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
        ),
        SensorEntityDescription(
            key="energy_consumed",
            name="Energy Export",
            icon="mdi:transmission-tower",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
        ),
        SensorEntityDescription(
            key="energy_consumed_solar",
            name="Energy Export Solar",
            icon="mdi:transmission-tower",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
        ),
        SensorEntityDescription(
            key="energy_consumed_battery",
            name="Energy Export Battery",
            icon="mdi:transmission-tower",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
            entity_registry_enabled_default=False,
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
            key="power_consumption",
            name="Power Export",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            device_class=SensorDeviceClass.POWER,
        ),
        SensorEntityDescription(
            key="power_consumption_solar",
            name="Power Export Solar",
            icon="mdi:solar-power",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            device_class=SensorDeviceClass.POWER,
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
            device_class=SensorDeviceClass.POWER_FACTOR,
        ),
        SensorEntityDescription(
            key="power_factor_b",
            name="Power Factor B",
            state_class=SensorStateClass.MEASUREMENT,
            device_class=SensorDeviceClass.POWER_FACTOR,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="power_factor_c",
            name="Power Factor C",
            state_class=SensorStateClass.MEASUREMENT,
            device_class=SensorDeviceClass.POWER_FACTOR,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="voltage_a",
            name="Voltage A",
            state_class=SensorStateClass.MEASUREMENT,
            device_class=SensorDeviceClass.VOLTAGE,
        ),
        SensorEntityDescription(
            key="voltage_b",
            name="Voltage B",
            state_class=SensorStateClass.MEASUREMENT,
            device_class=SensorDeviceClass.VOLTAGE,
            entity_registry_enabled_default=False,
        ),
        SensorEntityDescription(
            key="voltage_c",
            name="Voltage C",
            state_class=SensorStateClass.MEASUREMENT,
            device_class=SensorDeviceClass.VOLTAGE,
            entity_registry_enabled_default=False,
        ),
    ],
    "GENERIC_CONSUMER": SENSOR_DESCRIPTIONS_GENERIC_CONSUMER,
    "ENERGY_BALANCE": SENSOR_DESCRIPTIONS_GENERIC_CONSUMER,
}
