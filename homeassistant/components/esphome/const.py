"""ESPHome constants."""

from awesomeversion import AwesomeVersion

DOMAIN = "esphome"

CONF_ALLOW_SERVICE_CALLS = "allow_service_calls"
CONF_DEVICE_NAME = "device_name"
CONF_NOISE_PSK = "noise_psk"

DEFAULT_ALLOW_SERVICE_CALLS = True
DEFAULT_NEW_CONFIG_ALLOW_ALLOW_SERVICE_CALLS = False


STABLE_BLE_VERSION_STR = "2023.8.0"
STABLE_BLE_VERSION = AwesomeVersion(STABLE_BLE_VERSION_STR)
PROJECT_URLS = {
    "esphome.bluetooth-proxy": "https://esphome.github.io/bluetooth-proxies/",
}
DEFAULT_URL = f"https://esphome.io/changelog/{STABLE_BLE_VERSION_STR}.html"

DATA_FFMPEG_PROXY = f"{DOMAIN}.ffmpeg_proxy"
