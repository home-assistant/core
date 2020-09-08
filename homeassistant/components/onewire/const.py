"""Constants for the 1-Wire component."""
import logging

CONF_MOUNT_DIR = "mount_dir"
CONF_NAMES = "names"

CONF_TYPE_OWFS = "OWFS"
CONF_TYPE_OWSERVER = "OWServer"
CONF_TYPE_SYSBUS = "SysBus"

DEFAULT_HOST = "localhost"
DEFAULT_OWFS_MOUNT_DIR = "/mnt/1wire"
DEFAULT_PORT = 4304
DEFAULT_SYSBUS_MOUNT_DIR = "/sys/bus/w1/devices/"

DOMAIN = "onewire"

LOGGER = logging.getLogger(__package__)

SUPPORTED_PLATFORMS = [
    "sensor",
]
