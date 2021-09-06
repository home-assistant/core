"""The Ted6000 component."""

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntityDescription,
)
from homeassistant.const import DEVICE_CLASS_ENERGY, ENERGY_WATT_HOUR, POWER_WATT
from homeassistant.util import dt

DOMAIN = "ted6000"
PLATFORMS = ["sensor"]

COORDINATOR = "coordinator"
NAME = "name"

SENSORS = (
    SensorEntityDescription(
        key="consumption",
        name="Current Energy Consumption",
        native_unit_of_measurement=POWER_WATT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="daily_consumption",
        name="Today's Energy Consumption",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        state_class=STATE_CLASS_MEASUREMENT,
        device_class=DEVICE_CLASS_ENERGY,
        last_reset=dt.start_of_local_day(),
    ),
    SensorEntityDescription(
        key="mtd_consumption",
        name="Month to Date Energy Production",
        native_unit_of_measurement=ENERGY_WATT_HOUR,
        state_class=STATE_CLASS_MEASUREMENT,
        device_class=DEVICE_CLASS_ENERGY,
    ),
)
