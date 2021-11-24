"""The enphase_envoy component."""


from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntityDescription,
)
from homeassistant.const import DEVICE_CLASS_ENERGY, ENERGY_WATT_HOUR, POWER_WATT

DOMAIN = "enphase_envoy"

PLATFORMS = ["sensor"]


COORDINATOR = "coordinator"
NAME = "name"

SENSORS = (
    SensorEntityDescription(
        key="production",
        name="Current Power Production",
        native_unit_of_measurement=POWER_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="daily_production",
        name="Today's Energy Production",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    SensorEntityDescription(
        key="seven_days_production",
        name="Last Seven Days Energy Production",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        state_class=STATE_CLASS_MEASUREMENT,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    SensorEntityDescription(
        key="lifetime_production",
        name="Lifetime Energy Production",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    SensorEntityDescription(
        key="consumption",
        name="Current Power Consumption",
        native_unit_of_measurement=POWER_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="daily_consumption",
        name="Today's Energy Consumption",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        state_class=STATE_CLASS_MEASUREMENT,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    SensorEntityDescription(
        key="seven_days_consumption",
        name="Last Seven Days Energy Consumption",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        state_class=STATE_CLASS_MEASUREMENT,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    SensorEntityDescription(
        key="lifetime_consumption",
        name="Lifetime Energy Consumption",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    SensorEntityDescription(
        key="inverters",
        name="Inverter",
        native_unit_of_measurement=POWER_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
)
