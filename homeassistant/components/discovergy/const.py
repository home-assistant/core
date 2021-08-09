"""Constants for the Discovergy integration."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    STATE_CLASS_MEASUREMENT,
    SensorEntityDescription,
)
from homeassistant.const import ENERGY_KILO_WATT_HOUR, POWER_WATT
from homeassistant.util.dt import utc_from_timestamp

DOMAIN = "discovergy"
MANUFACTURER = "Discovergy"
APP_NAME = "homeassistant"
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

CONF_CONSUMER_KEY = "consumer_key"
CONF_CONSUMER_SECRET = "consumer_secret"
CONF_ACCESS_TOKEN = "access_token"
CONF_ACCESS_TOKEN_SECRET = "access_token_secret"

ELECTRICITY_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="power",
        name="Total power",
        unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="power1",
        name="Phase 1 power",
        unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="power2",
        name="Phase 2 power",
        unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="power3",
        name="Phase 3 power",
        unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="energy",
        name="Total consumption",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_MEASUREMENT,
        last_reset=utc_from_timestamp(0),
    ),
    SensorEntityDescription(
        key="energyOut",
        name="Total production",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_MEASUREMENT,
        last_reset=utc_from_timestamp(0),
    ),
)
