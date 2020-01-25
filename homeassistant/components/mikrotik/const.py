"""Constants used in the Mikrotik components."""

DOMAIN = "mikrotik"
MIKROTIK = DOMAIN
HOSTS = "hosts"
MTK_LOGIN_PLAIN = "plain"
MTK_LOGIN_TOKEN = "token"

CONF_ARP_PING = "arp_ping"
CONF_TRACK_DEVICES = "track_devices"
CONF_LOGIN_METHOD = "login_method"
CONF_ENCODING = "encoding"
DEFAULT_ENCODING = "utf-8"

NAME = "name"
INFO = "info"
IDENTITY = "identity"
ARP = "arp"
DHCP = "dhcp"
WIRELESS = "wireless"
CAPSMAN = "capsman"

MIKROTIK_SERVICES = {
    INFO: "/system/routerboard/getall",
    IDENTITY: "/system/identity/getall",
    ARP: "/ip/arp/getall",
    DHCP: "/ip/dhcp-server/lease/getall",
    WIRELESS: "/interface/wireless/registration-table/getall",
    CAPSMAN: "/caps-man/registration-table/getall",
}

ATTR_DEVICE_TRACKER = [
    "comment",
    "mac-address",
    "ssid",
    "interface",
    "host-name",
    "last-seen",
    "rx-signal",
    "signal-strength",
    "tx-ccq",
    "signal-to-noise",
    "wmm-enabled",
    "authentication-type",
    "encryption",
    "tx-rate-set",
    "rx-rate",
    "tx-rate",
    "uptime",
]
