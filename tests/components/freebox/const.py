"""Test constants."""


from tests.common import load_json_array_fixture, load_json_object_fixture

MOCK_HOST = "myrouter.freeboxos.fr"
MOCK_PORT = 1234

# router
DATA_SYSTEM_GET_CONFIG = load_json_object_fixture("freebox/system_get_config.json")

# sensors
DATA_CONNECTION_GET_STATUS = load_json_object_fixture(
    "freebox/connection_get_status.json"
)

DATA_CALL_GET_CALLS_LOG = load_json_array_fixture("freebox/call_get_calls_log.json")

DATA_STORAGE_GET_DISKS = load_json_array_fixture("freebox/storage_get_disks.json")

DATA_STORAGE_GET_RAIDS = load_json_array_fixture("freebox/storage_get_raids.json")

# switch
WIFI_GET_GLOBAL_CONFIG = load_json_object_fixture("freebox/wifi_get_global_config.json")

# device_tracker
DATA_LAN_GET_HOSTS_LIST = load_json_array_fixture("freebox/lan_get_hosts_list.json")


# Home
# ALL
DATA_HOME_GET_NODES = load_json_array_fixture("freebox/home_get_nodes.json")

# Home
# PIR node id 26, endpoint id 6
DATA_HOME_PIR_GET_VALUES = load_json_object_fixture("freebox/home_pir_get_values.json")

# Home
# ALARM node id 7, endpoint id 11
DATA_HOME_ALARM_GET_VALUES = load_json_object_fixture(
    "freebox/home_alarm_get_values.json"
)
