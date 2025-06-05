"""ESPHome constants."""

from typing import Final

from awesomeversion import AwesomeVersion

DOMAIN = "esphome"

CONF_ALLOW_SERVICE_CALLS = "allow_service_calls"
CONF_SUBSCRIBE_LOGS = "subscribe_logs"
CONF_DEVICE_NAME = "device_name"
CONF_NOISE_PSK = "noise_psk"
CONF_BLUETOOTH_MAC_ADDRESS = "bluetooth_mac_address"

DEFAULT_ALLOW_SERVICE_CALLS = True
DEFAULT_NEW_CONFIG_ALLOW_ALLOW_SERVICE_CALLS = False

DEFAULT_PORT: Final = 6053

STABLE_BLE_VERSION_STR = "2025.5.0"
STABLE_BLE_VERSION = AwesomeVersion(STABLE_BLE_VERSION_STR)
PROJECT_URLS = {
    "esphome.bluetooth-proxy": "https://esphome.github.io/bluetooth-proxies/",
}
# ESPHome always uses .0 for the changelog URL
STABLE_BLE_URL_VERSION = f"{STABLE_BLE_VERSION.major}.{STABLE_BLE_VERSION.minor}.0"
DEFAULT_URL = f"https://esphome.io/changelog/{STABLE_BLE_URL_VERSION}.html"
