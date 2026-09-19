"""Constants for the Netis Router integration.

This module centralises all configuration keys, ubus endpoint identifiers,
timing constants, and platform definitions used across the integration.

Key concepts:
  * **ubus over HTTP**: The router exposes a single JSON-RPC 2.0 endpoint
    (``POST /ubus``) backed by an OpenWrt ubus daemon. Each "namespace.method"
    pair (e.g. ``routerd.info``) maps to a specific router capability.
  * **AES-CBC authentication**: Before login, the client fetches a random key
    from ``rkey.get_rand_key``, uses it to AES-128-CBC encrypt the password,
    and submits the ciphertext to ``rkey.session.login``.
  * **Session token**: Login returns ``ubus_rpc_session`` (32-char hex),
    valid for 300 seconds. All subsequent requests carry it in ``params[0]``.
"""

DOMAIN = "netis"

# Config entry fields
CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

DEFAULT_HOST = "192.168.1.1"
DEFAULT_USERNAME = "root"

# ubus session token used before login
ANONYMOUS_TOKEN = "00000000000000000000000000000000"

# AES-CBC parameters (from router firmware: js/publicPlugin/dLoad.js)
AES_IV = b"poiewjhw49q35j4n"
LOGIN_TIMEOUT = 15
DEFAULT_SCAN_INTERVAL = 30  # seconds
# uci.apply reloads the wireless subsystem and can block; cap how long we
# wait for its reply before treating it as a background task.
WIFI_APPLY_TIMEOUT = 8  # seconds
# Whole write (uci.set + apply) can block on this firmware (rpcd serialises
# writes); cap the end-to-end operation so Home Assistant never hangs.
WRITE_TIMEOUT = 12  # seconds

# ubus error codes
ERR_OK = 0
ERR_PERMISSION_DENIED = 6  # token expired / unauthorized -> re-login

# ubus namespace.method constants used by this integration
UBUS_SYSTEM_INFO = ("routerd", "info")
UBUS_HOSTS = ("devices_app", "get_host_info")
UBUS_MWAN3 = ("mwan3", "status")
UBUS_LTE_INFO = ("lte_ubus", "LteInfo")
UBUS_CUSTOMER = ("uci", "get")
UBUS_REBOOT = ("system", "reboot")
UBUS_WIFI_CFG = ("uci", "get")          # {"config": "wificfg"}

# WiFi bands (uci section names inside the `wificfg` config)
BAND_2G = "2G"
BAND_5G = "5G"
WIFI_BANDS = (BAND_2G, BAND_5G)

# Valid Transmit Power levels supported by the firmware
# (see signal_conditioning.html data-power options: 2/50/100 = low/mid/high)
TXPOWER_LEVELS = ("2", "50", "100")

# Manufacturer / model defaults
MANUFACTURER = "Netis"

# Platforms
PLATFORM_DEVICE_TRACKER = "device_tracker"
PLATFORM_SENSOR = "sensor"
PLATFORM_BINARY_SENSOR = "binary_sensor"
PLATFORM_BUTTON = "button"
PLATFORM_SWITCH = "switch"
PLATFORM_SELECT = "select"

PLATFORMS = (
    PLATFORM_DEVICE_TRACKER,
    PLATFORM_SENSOR,
    PLATFORM_BINARY_SENSOR,
    PLATFORM_BUTTON,
    PLATFORM_SWITCH,
    PLATFORM_SELECT,
)
