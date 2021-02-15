"""AsusWrt component constants."""
DOMAIN = "asuswrt"

CONF_DNSMASQ = "dnsmasq"
CONF_INTERFACE = "interface"
CONF_REQUIRE_IP = "require_ip"
CONF_SSH_KEY = "ssh_key"
CONF_TRACK_UNKNOWN = "track_unknown"

DATA_ASUSWRT = DOMAIN

DEFAULT_DNSMASQ = "/var/lib/misc"
DEFAULT_INTERFACE = "eth0"
DEFAULT_SSH_PORT = 22
DEFAULT_TRACK_UNKNOWN = False

MODE_AP = "ap"
MODE_ROUTER = "router"

PROTOCOL_SSH = "ssh"
PROTOCOL_TELNET = "telnet"

# Sensor
SENSOR_TYPES = ["devices", "upload_speed", "download_speed", "download", "upload"]
