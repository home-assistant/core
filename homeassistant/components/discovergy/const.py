"""Constants for the Discovergy integration."""
from datetime import timedelta
from typing import Dict

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

ELECTRICITY_SENSORS: Dict[str, SensorEntityDescription] = {
    "power": SensorEntityDescription(
        key="power_consumption_total",
        name="Total power",
        unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        icon="mdi:power-plug",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "power1": SensorEntityDescription(
        key="power_consumption_phase1",
        name="Phase 1 power",
        unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        icon="mdi:power-plug",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "power2": SensorEntityDescription(
        key="power_consumption_phase2",
        name="Phase 2 power",
        unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        icon="mdi:power-plug",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "power3": SensorEntityDescription(
        key="power_consumption_phase3",
        name="Phase 3 power",
        unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        icon="mdi:power-plug",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "energy": SensorEntityDescription(
        key="total_energy_consumed",
        name="Total consumption",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        icon="mdi:power-plug",
        state_class=STATE_CLASS_MEASUREMENT,
        last_reset=utc_from_timestamp(0),
    ),
    "energyOut": SensorEntityDescription(
        key="total_energy_produced",
        name="Total production",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        icon="mdi:power-plug",
        state_class=STATE_CLASS_MEASUREMENT,
        last_reset=utc_from_timestamp(0),
    ),
}
