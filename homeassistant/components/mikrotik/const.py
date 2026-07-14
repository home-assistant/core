"""Constants used in the Mikrotik components."""

from typing import Final

DOMAIN: Final = "mikrotik"
DEFAULT_NAME: Final = "Mikrotik"
DEFAULT_API_PORT: Final = 8728
DEFAULT_DETECTION_TIME: Final = 300

ATTR_MANUFACTURER: Final = "Mikrotik"
ATTR_SERIAL_NUMBER: Final = "serial-number"
ATTR_FIRMWARE: Final = "current-firmware"

CONF_ARP_PING: Final = "arp_ping"
CONF_FORCE_DHCP: Final = "force_dhcp"
CONF_DETECTION_TIME: Final = "detection_time"

NAME: Final = "name"

ARP: Final = "arp"
CAPSMAN: Final = "capsman"
DHCP: Final = "dhcp"
HEALTH: Final = "health"
IDENTITY: Final = "identity"
INFO: Final = "info"
IS_CAPSMAN: Final = "is_capsman"
IS_WIFI: Final = "is_wifi"
IS_WIFIWAVE2: Final = "is_wifiwave2"
IS_WIRELESS: Final = "is_wireless"
SYSTEM: Final = "system"
WIFI: Final = "wifi"
WIFIWAVE2: Final = "wifiwave2"
WIRELESS: Final = "wireless"


MIKROTIK_SERVICES: Final = {
    ARP: "/ip/arp/getall",
    CAPSMAN: "/caps-man/registration-table/getall",
    DHCP: "/ip/dhcp-server/lease/getall",
    HEALTH: "/system/health/print",
    IDENTITY: "/system/identity/getall",
    INFO: "/system/routerboard/getall",
    IS_CAPSMAN: "/caps-man/interface/print",
    IS_WIFI: "/interface/wifi/print",
    IS_WIFIWAVE2: "/interface/wifiwave2/print",
    IS_WIRELESS: "/interface/wireless/print",
    SYSTEM: "/system/resource/print",
    WIFI: "/interface/wifi/registration-table/print",
    WIFIWAVE2: "/interface/wifiwave2/registration-table/print",
    WIRELESS: "/interface/wireless/registration-table/getall",
}


ATTR_DEVICE_TRACKER: Final = [
    "comment",
    "ssid",
    "interface",
    "signal-strength",
    "signal-to-noise",
    "rx-rate",
    "tx-rate",
    "uptime",
]
