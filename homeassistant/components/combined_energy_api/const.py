"""Constants for the Combined Energy API integration."""
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
from homeassistant.const import UnitOfPower, UnitOfTemperature, UnitOfVolume

DOMAIN: Final[str] = "combined_energy_api"

LOGGER = logging.getLogger(__package__)

# Data for combined energy api requests.
DATA_API_CLIENT: Final[str] = "api_client"
DATA_INSTALLATION: Final[str] = "installation"

# Config for combined energy api requests.
CONF_INSTALLATION_ID: Final[str] = "installation_id"
DEFAULT_NAME: Final[str] = "Combined Energy"

CONNECTIVITY_UPDATE_DELAY: Final[timedelta] = timedelta(seconds=30)
READINGS_UPDATE_DELAY: Final[timedelta] = timedelta(seconds=30)

READINGS_INCREMENT: Final[int] = 5

# Supported overview sensors
SENSOR_TYPE_CONNECTED = BinarySensorEntityDescription(
    key="connected",
    name="Monitor Connected",
    icon="mdi:wifi-cog",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
)
SENSOR_TYPE_GENERIC_CONSUMER = [
    SensorEntityDescription(
        key="energy_consumed",
        name="Power Consumption",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    SensorEntityDescription(
        key="energy_consumed_solar",
        name="Solar Consumption",
        icon="mdi:solar-power",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    SensorEntityDescription(
        key="energy_consumed_battery",
        name="Battery Consumption",
        icon="mdi:home-battery",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
]
SENSOR_TYPES = {
    "SOLAR_PV": [
        SensorEntityDescription(
            key="energy_supplied",
            name="Energy Supplied",
            icon="mdi:solar-power",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            device_class=SensorDeviceClass.POWER,
        )
    ],
    "WATER_HEATER": SENSOR_TYPE_GENERIC_CONSUMER
    + [
        SensorEntityDescription(
            key="energy_consumed_grid",
            name="Grid Consumption",
            icon="mdi:transmission-tower",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            device_class=SensorDeviceClass.POWER,
        ),
        SensorEntityDescription(
            key="available_energy",
            name="Hot Water Available",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfVolume.LITERS,
            device_class=SensorDeviceClass.WATER,
        ),
        SensorEntityDescription(
            key="temp_sensor1",
            name="Water Temp 1",
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
    ],
    "GRID_METER": [
        SensorEntityDescription(
            key="energy_supplied",
            name="Energy Supplied",
            icon="mdi:transmission-tower",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            device_class=SensorDeviceClass.POWER,
        ),
        SensorEntityDescription(
            key="energy_consumed",
            name="Power Consumption",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            device_class=SensorDeviceClass.POWER,
        ),
        SensorEntityDescription(
            key="energy_consumed_solar",
            name="Power Consumption Solar",
            icon="mdi:solar-power",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            device_class=SensorDeviceClass.POWER,
        ),
        SensorEntityDescription(
            key="energy_consumed_battery",
            name="Power Consumption Battery",
            icon="mdi:home-battery",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            device_class=SensorDeviceClass.POWER,
        ),
        SensorEntityDescription(
            key="energy_consumed_grid",
            name="Power Consumption Grid",
            icon="mdi:transmission-tower",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            device_class=SensorDeviceClass.POWER,
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
        ),
        SensorEntityDescription(
            key="power_factor_c",
            name="Power Factor C",
            state_class=SensorStateClass.MEASUREMENT,
            device_class=SensorDeviceClass.POWER_FACTOR,
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
        ),
        SensorEntityDescription(
            key="voltage_c",
            name="Voltage C",
            state_class=SensorStateClass.MEASUREMENT,
            device_class=SensorDeviceClass.VOLTAGE,
        ),
    ],
    "GENERIC_CONSUMER": SENSOR_TYPE_GENERIC_CONSUMER
    + [
        SensorEntityDescription(
            key="energy_consumed_grid",
            name="Grid Consumption",
            icon="mdi:transmission-tower",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            device_class=SensorDeviceClass.POWER,
        ),
    ],
    "ENERGY_BALANCE": SENSOR_TYPE_GENERIC_CONSUMER
    + [
        SensorEntityDescription(
            key="energy_consumed_grid",
            name="Grid Consumption",
            icon="mdi:transmission-tower",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
            device_class=SensorDeviceClass.POWER,
        ),
    ],
}
