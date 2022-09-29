"""Constants for the Awair component."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from python_awair.air_data import AirData
from python_awair.devices import AwairBaseDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    SOUND_PRESSURE_WEIGHTED_DBA,
    TEMP_CELSIUS,
)

API_CO2 = "carbon_dioxide"
API_DUST = "dust"
API_HUMID = "humidity"
API_LUX = "illuminance"
API_PM10 = "particulate_matter_10"
API_PM25 = "particulate_matter_2_5"
API_SCORE = "score"
API_SPL_A = "sound_pressure_level"
API_TEMP = "temperature"
API_TIMEOUT = 20
API_VOC = "volatile_organic_compounds"

ATTRIBUTION = "Awair air quality sensor"

DOMAIN = "awair"

DUST_ALIASES = [API_PM25, API_PM10]

LOGGER = logging.getLogger(__package__)

UPDATE_INTERVAL_CLOUD = timedelta(minutes=5)
UPDATE_INTERVAL_LOCAL = timedelta(seconds=30)


@dataclass
class AwairRequiredKeysMixin:
    """Mixin for required keys."""

    unique_id_tag: str


@dataclass
class AwairSensorEntityDescription(SensorEntityDescription, AwairRequiredKeysMixin):
    """Describes Awair sensor entity."""


SENSOR_TYPE_SCORE = AwairSensorEntityDescription(
    key=API_SCORE,
    icon="mdi:blur",
    native_unit_of_measurement=PERCENTAGE,
    name="Score",
    unique_id_tag="score",  # matches legacy format
    state_class=SensorStateClass.MEASUREMENT,
)

SENSOR_TYPES: tuple[AwairSensorEntityDescription, ...] = (
    AwairSensorEntityDescription(
        key=API_HUMID,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        name="Humidity",
        unique_id_tag="HUMID",  # matches legacy format
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AwairSensorEntityDescription(
        key=API_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        name="Illuminance",
        unique_id_tag="illuminance",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AwairSensorEntityDescription(
        key=API_SPL_A,
        icon="mdi:ear-hearing",
        native_unit_of_measurement=SOUND_PRESSURE_WEIGHTED_DBA,
        name="Sound level",
        unique_id_tag="sound_level",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AwairSensorEntityDescription(
        key=API_VOC,
        icon="mdi:molecule",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        name="Volatile organic compounds",
        unique_id_tag="VOC",  # matches legacy format
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AwairSensorEntityDescription(
        key=API_TEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        name="Temperature",
        unique_id_tag="TEMP",  # matches legacy format
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AwairSensorEntityDescription(
        key=API_CO2,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        name="Carbon dioxide",
        unique_id_tag="CO2",  # matches legacy format
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

SENSOR_TYPES_DUST: tuple[AwairSensorEntityDescription, ...] = (
    AwairSensorEntityDescription(
        key=API_PM25,
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        name="PM2.5",
        unique_id_tag="PM25",  # matches legacy format
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AwairSensorEntityDescription(
        key=API_PM10,
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        name="PM10",
        unique_id_tag="PM10",  # matches legacy format
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


@dataclass
class AwairResult:
    """Wrapper class to hold an awair device and set of air data."""

    device: AwairBaseDevice
    air_data: AirData
