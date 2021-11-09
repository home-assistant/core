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

# Sensors
SENSORS_BYTES = ["sensor_rx_bytes", "sensor_tx_bytes"]
SENSORS_CONNECTED_DEVICE = ["sensor_connected_device"]
SENSORS_LOAD_AVG = ["sensor_load_avg1", "sensor_load_avg5", "sensor_load_avg15"]
SENSORS_RATES = ["sensor_rx_rates", "sensor_tx_rates"]
