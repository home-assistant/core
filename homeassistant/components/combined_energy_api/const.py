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
from homeassistant.const import UnitOfEnergy, UnitOfPower, UnitOfTemperature

DOMAIN: Final[str] = "combined_energy_api"

LOGGER = logging.getLogger(__package__)

# Data for combined energy api requests.
DATA_API_CLIENT: Final[str] = "api_client"
DATA_INSTALLATION: Final[str] = "installation"

# Config for combined energy api requests.
CONF_INSTALLATION_ID: Final[str] = "installation_id"
DEFAULT_NAME: Final[str] = "Combined Energy API"

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
    "WATER_HEATER": [
        SensorEntityDescription(
            key="energy_consumed",
            name="Energy Consumed",
            # icon="mdi:solar-power",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
        ),
        SensorEntityDescription(
            key="energy_consumed_solar",
            name="Energy Consumed Solar",
            icon="mdi:solar-power",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
        ),
        SensorEntityDescription(
            key="energy_consumed_battery",
            name="Energy Consumed Battery",
            icon="mdi:home-battery",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
        ),
        SensorEntityDescription(
            key="energy_consumed_grid",
            name="Energy Consumed Grid",
            icon="mdi:transmission-tower",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
        ),
        SensorEntityDescription(
            key="available_energy",
            name="Available Energy",
            icon="mdi:lightning-bolt",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
        ),
        SensorEntityDescription(
            key="max_energy",
            name="Max Energy",
            icon="mdi:lightning-bolt-circle",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            device_class=SensorDeviceClass.ENERGY,
        ),
        SensorEntityDescription(
            key="temp_sensor1",
            name="Temp Level 1",
            icon="mdi:thermometer-water",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
        ),
        SensorEntityDescription(
            key="temp_sensor2",
            name="Temp Level 2",
            icon="mdi:thermometer-water",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
        ),
        SensorEntityDescription(
            key="temp_sensor3",
            name="Temp Level 3",
            icon="mdi:thermometer-water",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
        ),
        SensorEntityDescription(
            key="temp_sensor4",
            name="Temp Level 4",
            icon="mdi:thermometer-water",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
        ),
        SensorEntityDescription(
            key="temp_sensor5",
            name="Temp Level 5",
            icon="mdi:thermometer-water",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
        ),
        SensorEntityDescription(
            key="temp_sensor6",
            name="Temp Level 6",
            icon="mdi:thermometer-water",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
        ),
    ],
}
