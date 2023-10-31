"""Test constants."""

from homeassistant.components.freebox.const import DOMAIN

from tests.common import load_json_object_fixture

MOCK_HOST = "myrouter.freeboxos.fr"
MOCK_PORT = 1234

# router
DATA_SYSTEM_GET_CONFIG = load_json_object_fixture("system_get_config.json", DOMAIN)

# sensors
DATA_CONNECTION_GET_STATUS = load_json_object_fixture(
    "connection_get_status.json", DOMAIN
)

DATA_CALL_GET_CALLS_LOG = load_json_object_fixture("call_get_calls_log.json", DOMAIN)

DATA_STORAGE_GET_DISKS = load_json_object_fixture("storage_get_disks.json", DOMAIN)

DATA_STORAGE_GET_RAIDS = load_json_object_fixture("storage_get_raids.json", DOMAIN)

# switch
WIFI_GET_GLOBAL_CONFIG = load_json_object_fixture("wifi_get_global_config.json", DOMAIN)

# device_tracker
DATA_LAN_GET_HOSTS_LIST = load_json_object_fixture("lan_get_hosts_list.json", DOMAIN)


# Home
# ALL
DATA_HOME_GET_NODES = load_json_object_fixture("home_get_nodes.json", DOMAIN)

# Home
# PIR node id 26, endpoint id 6
DATA_HOME_PIR_GET_VALUES = load_json_object_fixture("home_pir_get_values.json", DOMAIN)

# Home
# ALARM node id 7, endpoint id 11
DATA_HOME_ALARM_GET_VALUES = load_json_object_fixture(
    "home_alarm_get_values.json", DOMAIN
)
