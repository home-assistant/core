"""The enphase_envoy component."""


from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntityDescription,
)
from homeassistant.const import ENERGY_WATT_HOUR, POWER_WATT
from homeassistant.util import dt

DOMAIN = "enphase_envoy"

PLATFORMS = ["sensor"]


COORDINATOR = "coordinator"
NAME = "name"

SENSORS = {
    "production": ("Current Energy Production", POWER_WATT, STATE_CLASS_MEASUREMENT),
    "daily_production": ("Today's Energy Production", ENERGY_WATT_HOUR, None),
    "seven_days_production": (
        "Last Seven Days Energy Production",
        ENERGY_WATT_HOUR,
        None,
    ),
    "lifetime_production": ("Lifetime Energy Production", ENERGY_WATT_HOUR, None),
    "consumption": ("Current Energy Consumption", POWER_WATT, STATE_CLASS_MEASUREMENT),
    "daily_consumption": ("Today's Energy Consumption", ENERGY_WATT_HOUR, None),
    "seven_days_consumption": (
        "Last Seven Days Energy Consumption",
        ENERGY_WATT_HOUR,
        None,
    ),
    "lifetime_consumption": ("Lifetime Energy Consumption", ENERGY_WATT_HOUR, None),
    "inverters": ("Inverter", POWER_WATT, STATE_CLASS_MEASUREMENT),
}

SENSORS = (
    SensorEntityDescription(
        key="production",
        name="Current Energy Production",
        unit_of_measurement=POWER_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="daily_production",
        name="Today's Energy Production",
        unit_of_measurement=ENERGY_WATT_HOUR,
        state_class=None,
    ),
    SensorEntityDescription(
        key="seven_days_production",
        name="Last Seven Days Energy Production",
        unit_of_measurement=ENERGY_WATT_HOUR,
        state_class=None,
    ),
    SensorEntityDescription(
        key="lifetime_production",
        name="Lifetime Energy Production",
        unit_of_measurement=ENERGY_WATT_HOUR,
        state_class=None,
        last_reset=dt.utc_from_timestamp(0),
    ),
    SensorEntityDescription(
        key="consumption",
        name="Current Energy Consumption",
        unit_of_measurement=POWER_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="daily_consumption",
        name="Today's Energy Consumption",
        unit_of_measurement=ENERGY_WATT_HOUR,
        state_class=None,
    ),
    SensorEntityDescription(
        key="seven_days_consumption",
        name="Last Seven Days Energy Consumption",
        unit_of_measurement=ENERGY_WATT_HOUR,
        state_class=None,
    ),
    SensorEntityDescription(
        key="lifetime_consumption",
        name="Lifetime Energy Consumption",
        unit_of_measurement=ENERGY_WATT_HOUR,
        state_class=None,
        last_reset=dt.utc_from_timestamp(0),
    ),
    SensorEntityDescription(
        key="inverters",
        name="Inverter",
        unit_of_measurement=POWER_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
)
