"""Constants for Daikin."""

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

MODE_MANUAL = "manual"
MODE_AUTO = "auto"

DAIKIN_DEMAND_CONTROL_MODES: dict[str, int] = {
    MODE_MANUAL: 0,
    MODE_AUTO: 2,
}

KEY_MAC = "mac"
KEY_IP = "ip"

ZONE_NAME_UNCONFIGURED = "-"

TIMEOUT_SEC = 120
