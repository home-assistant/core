"""Constants for viaris integration."""

DOMAIN = "viaris"

CONF_SERIAL_NUMBER = "serial_number"
# CONF_USERNAME = "username"
# CONF_PASSWORD = "password"
# CONF_HOST = "host"
CONF_TOPIC_PREFIX = "topic_prefix"

DEFAULT_TOPIC_PREFIX = "XEO/VIARIS/"
DEFAULT_NAME = "VIARIS"

STATE_CONN1_KEY = "status_conn1"
USER_CONN1_KEY = "user_conn1"
ACTIVE_ENERGY_CONN1_KEY = "active_energy_conn1"
REACTIVE_ENERGY_CONN1_KEY = "reactive_energy_conn1"
STATE_CONN2_KEY = "status_conn2"
USER_CONN2_KEY = "user_conn2"
ACTIVE_ENERGY_CONN2_KEY = "active_energy_conn2"
REACTIVE_ENERGY_CONN2_KEY = "reactive_energy_conn2"
EVSE_POWER_KEY = "evse_power"
HOME_POWER_KEY = "home_power"
TOTAL_POWER_KEY = "total_power"
OVERLOAD_REL_KEY = "overload_rel"
TOTAL_CURRENT_KEY = "total_current"
TMC100_KEY = "tmc100"
CONTAX_D0613_KEY = "contax_d0613"
ACTIVE_POWER_CONN1_KEY = "active_power_conn1"
REACTIVE_POWER_CONN1_KEY = "reactive_power_conn2"
ACTIVE_POWER_CONN2_KEY = "active_power_conn2"
REACTIVE_POWER_CONN2_KEY = "reactive_power_conn2"


class ChargerStatusCodes:
    """Charger Mennekes Status Description."""

    mennekes = {
        0: "Standby",
        1: "Disconnected",
        2: "Disconnected without permission",
        3: "Connected ",
        4: "Connected with permission",
        5: "Charging",
        6: "Charging: power limit",
        7: "Paused charging",
        8: "Charging finished",
        9: "error",
        10: "error",
        11: "error",
        12: "error",
        13: "error",
    }
    schuko = {14: "chuko ON, LOAD", 30: "schuko ON, NOT LOAD", 31: "schuko OFF"}
