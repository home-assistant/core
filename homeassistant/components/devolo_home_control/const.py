"""Constants for the devolo_home_control integration."""
import re

DOMAIN = "devolo_home_control"
DEFAULT_MYDEVOLO = "https://www.mydevolo.com"
PLATFORMS = ["binary_sensor", "climate", "cover", "light", "sensor", "switch"]
CONF_MYDEVOLO = "mydevolo_url"
GATEWAY_SERIAL_PATTERN = re.compile(r"\d{16}")
