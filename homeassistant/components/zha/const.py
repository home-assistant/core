"""Constants for the ZHA integration."""

EZSP_OVERWRITE_EUI64 = (
    "i_understand_i_can_update_eui64_only_once_and_i_still_want_to_do_it"
)

ATTR_ACTIVE_COORDINATOR = "active_coordinator"
ATTR_ATTRIBUTES = "attributes"
ATTR_AVAILABLE = "available"
ATTR_DEVICE_TYPE = "device_type"
ATTR_CLUSTER_NAME = "cluster_name"
ATTR_ENDPOINT_NAMES = "endpoint_names"
ATTR_IEEE = "ieee"
ATTR_LAST_SEEN = "last_seen"
ATTR_LQI = "lqi"
ATTR_MANUFACTURER = "manufacturer"
ATTR_MANUFACTURER_CODE = "manufacturer_code"
ATTR_NEIGHBORS = "neighbors"
ATTR_NWK = "nwk"
ATTR_POWER_SOURCE = "power_source"
ATTR_QUIRK_APPLIED = "quirk_applied"
ATTR_QUIRK_CLASS = "quirk_class"
ATTR_QUIRK_ID = "quirk_id"
ATTR_ROUTES = "routes"
ATTR_RSSI = "rssi"
ATTR_SIGNATURE = "signature"
ATTR_SUCCESS = "success"


CONF_ALARM_MASTER_CODE = "alarm_master_code"
CONF_ALARM_FAILED_TRIES = "alarm_failed_tries"
CONF_ALARM_ARM_REQUIRES_CODE = "alarm_arm_requires_code"

CONF_RADIO_TYPE = "radio_type"
CONF_USB_PATH = "usb_path"
CONF_USE_THREAD = "use_thread"
CONF_BAUDRATE = "baudrate"
CONF_FLOW_CONTROL = "flow_control"

CONF_ENABLE_QUIRKS = "enable_quirks"
CONF_CUSTOM_QUIRKS_PATH = "custom_quirks_path"

CONF_DEFAULT_LIGHT_TRANSITION = "default_light_transition"
CONF_ENABLE_ENHANCED_LIGHT_TRANSITION = "enhanced_light_transition"
CONF_ENABLE_LIGHT_TRANSITIONING_FLAG = "light_transitioning_flag"
CONF_GROUP_MEMBERS_ASSUME_STATE = "group_members_assume_state"

CONF_ENABLE_IDENTIFY_ON_JOIN = "enable_identify_on_join"
CONF_CONSIDER_UNAVAILABLE_MAINS = "consider_unavailable_mains"
CONF_CONSIDER_UNAVAILABLE_BATTERY = "consider_unavailable_battery"
CONF_ENABLE_MAINS_STARTUP_POLLING = "enable_mains_startup_polling"

CONF_ZIGPY = "zigpy_config"
CONF_DEVICE_CONFIG = "device_config"

CUSTOM_CONFIGURATION = "custom_configuration"

DATA_ZHA = "zha"
DATA_ZHA_DEVICE_TRIGGER_CACHE = "zha_device_trigger_cache"

DEFAULT_DATABASE_NAME = "zigbee.db"

DEVICE_PAIRING_STATUS = "pairing_status"

DOMAIN = "zha"

GROUP_ID = "group_id"


GROUP_IDS = "group_ids"
GROUP_NAME = "group_name"

MFG_CLUSTER_ID_START = 0xFC00

ZHA_ALARM_OPTIONS = "zha_alarm_options"
ZHA_OPTIONS = "zha_options"
