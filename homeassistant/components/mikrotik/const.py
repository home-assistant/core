"""Constants used in the Mikrotik components."""

DOMAIN = "mikrotik"
MIKROTIK = DOMAIN
HOSTS = "hosts"
MTK_LOGIN_PLAIN = "plain"
MTK_LOGIN_TOKEN = "token"
MTK_DEFAULT_WAN = "ether1"

CONF_ARP_PING = "arp_ping"
CONF_TRACK_DEVICES = "track_devices"
CONF_LOGIN_METHOD = "login_method"
CONF_ENCODING = "encoding"
CONF_WAN_PORT = "wan_port"
DEFAULT_ENCODING = "utf-8"

INFO = "info"
IDENTITY = "identity"
ARP = "arp"
DHCP = "dhcp"
WIRELESS = "wireless"
CAPSMAN = "capsman"
RESOURCES = "resources"

MIKROTIK_SERVICES = {
    INFO: "/system/routerboard/getall",
    IDENTITY: "/system/identity/getall",
    ARP: "/ip/arp/getall",
    DHCP: "/ip/dhcp-server/lease/getall",
    WIRELESS: "/interface/wireless/registration-table/getall",
    CAPSMAN: "/caps-man/registration-table/getall",
    RESOURCES: "/system/resource/getall",
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

MEGA = 1048576

SENSOR_CPU = "cpu"
SENSOR_MEMORY = "memory"
SENSOR_DISK = "disk"
SENSOR_DOWNLOAD_SPEED = "download_speed"
SENSOR_UPLOAD_SPEED = "upload_speed"

UNITS = ["bits-per-second", "byte", "memory", "space"]

PARAM_SPEED = {"interface": MTK_DEFAULT_WAN, "duration": "1s"}

ATTR_CPU = ["cpu", "cpu-frequency", "cpu-count"]

ATTR_MEMORY = ["total-memory"]

ATTR_DISK = ["total-hdd-space"]

ATTR_DOWNLOAD_SPEED = [
    "name",
    "rx-packets-per-second",
    "fp-rx-packets-per-second",
    "rx-drops-per-second",
    "rx-errors-per-second",
]
ATTR_UPLOAD_SPEED = [
    "name",
    "tx-packets-per-second",
    "fp-tx-packets-per-second",
    "tx-drops-per-second",
    "tx-queue-drops-per-second",
    "tx-errors-per-second",
]

ATTR_DOWNLOAD = ["name", "tx-bytes"]

ATTR_UPLOAD = ["name", "rx-bytes"]

# Sensor types are defined like:
# Name, units, icon, state item, api cmd(s), ATTRutes
SENSORS = {
    SENSOR_CPU: [
        "CPU Load",
        "%",
        "mdi:chip",
        "cpu-load",
        [MIKROTIK_SERVICES[RESOURCES]],
        ATTR_CPU,
        None,
    ],
    SENSOR_MEMORY: [
        "Memory Free",
        "MiB",
        "mdi:memory",
        "free-memory",
        [MIKROTIK_SERVICES[RESOURCES]],
        ATTR_MEMORY,
        None,
    ],
    SENSOR_DISK: [
        "Disk Free",
        "MiB",
        "mdi:harddisk",
        "free-hdd-space",
        [MIKROTIK_SERVICES[RESOURCES]],
        ATTR_DISK,
        None,
    ],
    SENSOR_DOWNLOAD_SPEED: [
        "Download Speed",
        "Mbps",
        "mdi:download-network",
        "rx-bits-per-second",
        ["/interface/monitor-traffic"],
        ATTR_DOWNLOAD_SPEED,
        PARAM_SPEED,
    ],
    SENSOR_UPLOAD_SPEED: [
        "Upload Speed",
        "Mbps",
        "mdi:upload-network",
        "tx-bits-per-second",
        ["/interface/monitor-traffic"],
        ATTR_UPLOAD_SPEED,
        PARAM_SPEED,
    ],
}
