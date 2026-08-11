"""Constants for Daikin."""

import voluptuous as vol

from homeassistant.const import ATTR_MODE
from homeassistant.helpers.typing import VolDictType

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

SET_DEMAND_CONTROL_SCHEMA: VolDictType = {
    vol.Required(ATTR_EN_DEMAND): bool,
    vol.Required(ATTR_MAX_POW): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    vol.Optional(ATTR_MODE, default=0): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=2)
    ),
}

KEY_MAC = "mac"
KEY_IP = "ip"

ZONE_NAME_UNCONFIGURED = "-"

TIMEOUT_SEC = 120
