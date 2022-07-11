"""Constants for the Discovergy integration."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
    VOLUME_CUBIC_METERS,
)

DOMAIN = "discovergy"
MANUFACTURER = "Discovergy"
APP_NAME = "homeassistant"
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

API_CLIENT = "api_client"
METERS = "meters"
COORDINATORS = "coordinators"

CONF_CONSUMER_KEY = "consumer_key"
CONF_CONSUMER_SECRET = "consumer_secret"
CONF_ACCESS_TOKEN = "access_token"
CONF_ACCESS_TOKEN_SECRET = "access_token_secret"

GAS_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="volume",
        name="Total consumption",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)

ELECTRICITY_SENSORS: tuple[SensorEntityDescription, ...] = (
    # power sensors
    SensorEntityDescription(
        key="power",
        name="Total power",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="power1",
        name="Phase 1 power",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="power2",
        name="Phase 2 power",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="power3",
        name="Phase 3 power",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="phase1Power",
        name="Phase 1 power",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="phase2Power",
        name="Phase 2 power",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="phase3Power",
        name="Phase 3 power",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    # voltage sensors
    SensorEntityDescription(
        key="phase1Voltage",
        name="Phase 1 voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="phase2Voltage",
        name="Phase 2 voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="phase3Voltage",
        name="Phase 3 voltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    # energy sensors
    SensorEntityDescription(
        key="energy",
        name="Total consumption",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="energyOut",
        name="Total production",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)
