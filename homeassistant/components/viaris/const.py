"""Constants for viaris integration."""

DOMAIN = "viaris"

CONF_SERIAL_NUMBER = "serial_number"
ATTR_VALUE = "value"
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
REACTIVE_POWER_CONN1_KEY = "reactive_power_conn1"
ACTIVE_POWER_CONN2_KEY = "active_power_conn2"
REACTIVE_POWER_CONN2_KEY = "reactive_power_conn2"
FV_POWER_KEY = "solar_power_plus_bat"
FIRMWARE_APP_KEY = "fw_app"
HARDWARE_VERSION_KEY = "hw_version"
FW_POT_VERSION_KEY = "fw_pot_version"
HW_POT_VERSION_KEY = "hw_pot_version"
FW_CORTEX_VERSION_KEY = "fw_cortex_version"
SCHUKO_KEY = "Schuko_present"
RFID_KEY = "rfid"
ETHERNET_KEY = "ethernet"
SPL_KEY = "spl"
OCPP_KEY = "ocpp"
MODBUS_KEY = "modbus"
SOLAR_KEY = "solar"
KEEP_ALIVE_KEY = "keep_alive"
MQTT_PORT_KEY = "mqtt_port"
MQTT_QOS_KEY = "mqtt_qos"
MQTT_CLIENT_ID_KEY = "mqtt_client"
MQTT_USER_KEY = "mqtt_user"
PING_KEY = "mqtt_ping"
SERIAL_KEY = "serial_number"
MODEL_KEY = "model"
MAC_KEY = "mac"
MAX_POWER_KEY = "max_power"
LIMIT_POWER_KEY = "limit_power"
SELECTOR_POWER_KEY = "selector_power"
MQTT_URL_KEY = "mqtt_url"
DEVICE_INFO_MANUFACTURER = "Orbis"
DEVICE_INFO_MODEL = "Viaris UNI charger"
SERIAL_PREFIX_UNI = "EVVC3"
SERIAL_PREFIX_COMBI = "EVVC4"
MODEL_UNI = ("Uni",)
MODEL_COMBIPLUS = ("Combiplus",)


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
    schuko = {
        0: "Schuko Standby",
        14: "Schuko ON, LOAD",
        30: "Schuko ON, NOT LOAD",
        31: "Schuko OFF",
    }
