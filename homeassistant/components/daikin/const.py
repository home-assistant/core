"""Constants for Daikin."""

import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID, ATTR_MODE
from homeassistant.helpers import config_validation as cv

DOMAIN = "daikin"

ATTR_TARGET_TEMPERATURE = "target_temperature"
ATTR_INSIDE_TEMPERATURE = "inside_temperature"
ATTR_OUTSIDE_TEMPERATURE = "outside_temperature"

ATTR_TARGET_HUMIDITY = "target_humidity"
ATTR_HUMIDITY = "humidity"

ATTR_COMPRESSOR_FREQUENCY = "compressor_frequency"

ATTR_ENERGY_TODAY = "energy_today"
ATTR_COOL_ENERGY = "cool_energy"
ATTR_HEAT_ENERGY = "heat_energy"

ATTR_TOTAL_POWER = "total_power"
ATTR_TOTAL_ENERGY_TODAY = "total_energy_today"

ATTR_STATE_ON = "on"
ATTR_STATE_OFF = "off"

SERVICE_SET_DEMAND_CONTROL = "set_demand_control"
ATTR_EN_DEMAND = "en_demand"
ATTR_MAX_POW = "max_pow"

ATTR_MODE_MANUAL = "manual"
ATTR_MODE_SCHEDULED = "scheduled"
ATTR_MODE_AUTO = "auto"

DAIKIN_DEMAND_CONTROL_MODES = {
    ATTR_MODE_MANUAL: 0,
    ATTR_MODE_SCHEDULED: 1,
    ATTR_MODE_AUTO: 2,
}

SET_DEMAND_CONTROL_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_EN_DEMAND): bool,
        vol.Required(ATTR_MAX_POW): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional(ATTR_MODE, default=ATTR_MODE_MANUAL): vol.In(
            DAIKIN_DEMAND_CONTROL_MODES
        ),
    }
)

KEY_MAC = "mac"
KEY_IP = "ip"

ZONE_NAME_UNCONFIGURED = "-"

TIMEOUT_SEC = 120
