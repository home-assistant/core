"""Constants for the NeoPool integration."""

from neopool_modbus.capabilities import CAPABILITY_KEYS as LIB_CAPABILITY_KEYS

from homeassistant.const import Platform

DOMAIN = "neopool"
NAME = "NeoPool"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]

DEFAULT_SCAN_INTERVAL = 20  # in seconds
FOLLOW_UP_REFRESH_DELAY = 2.0  # seconds  (delay before a 2nd refresh for IO entity)
DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1

CONF_UNIT_ID = "unit_id"
CONF_MODBUS_FRAMER = "modbus_framer"

CONF_USE_LIGHT = "use_light"
CONF_USE_COVER_SENSOR = "use_cover_sensor"
CONF_USE_AUX1 = "use_aux1"
CONF_USE_AUX2 = "use_aux2"
CONF_USE_AUX3 = "use_aux3"
CONF_USE_AUX4 = "use_aux4"

# Winter mode is backed by the native config_entry.pref_disable_polling flag.
CONF_CAPABILITIES = "_capabilities"

CURRENT_VERSION = 6

# Persisted in entry.options for winter-mode restarts.
_CUSTOM_CAPABILITY_KEYS: tuple[str, ...] = (
    "MBF_PAR_HIDRO_NOM",
    "MBF_PAR_HIDRO_COVER_ENABLE",
    "MBF_PAR_PH_ACID_RELAY_GPIO",
    "MBF_PAR_PH_BASE_RELAY_GPIO",
    "MBF_PAR_RX_RELAY_GPIO",
    "MBF_PAR_CL_RELAY_GPIO",
    "MBF_PAR_CD_RELAY_GPIO",
    "MBF_PAR_UV_RELAY_GPIO",
    "MBF_PAR_RELAY_PH",
    "MBF_PAR_FILT_GPIO",
    "MBF_PAR_LIGHTING_GPIO",
    "MBF_POWER_MODULE_VERSION",
    "MBF_PAR_VERSION",
)

CAPABILITY_KEYS: tuple[str, ...] = tuple(
    dict.fromkeys((*LIB_CAPABILITY_KEYS, *_CUSTOM_CAPABILITY_KEYS))
)
