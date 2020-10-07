"""Constants for 1-Wire component."""
CONF_MOUNT_DIR = "mount_dir"
CONF_NAMES = "names"

DEFAULT_OWSERVER_PORT = 4304
DEFAULT_SYSBUS_MOUNT_DIR = "/sys/bus/w1/devices/"

DOMAIN = "onewire"

SUPPORTED_PLATFORMS = [
    "sensor",
]
