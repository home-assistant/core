"""Constants for 1-Wire component."""
CONF_MOUNT_DIR = "mount_dir"
CONF_NAMES = "names"

CONF_TYPE_OWFS = "OWFS"
CONF_TYPE_OWSERVER = "OWServer"
CONF_TYPE_SYSBUS = "SysBus"

DEFAULT_OWFS_MOUNT_DIR = "/mnt/1wire"
DEFAULT_OWSERVER_HOST = "localhost"
DEFAULT_OWSERVER_PORT = 4304
DEFAULT_SYSBUS_MOUNT_DIR = "/sys/bus/w1/devices/"

DOMAIN = "onewire"

SUPPORTED_PLATFORMS = [
    "sensor",
]
