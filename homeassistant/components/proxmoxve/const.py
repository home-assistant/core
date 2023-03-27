"""Constants for ProxmoxVE."""

import logging

from homeassistant.backports.enum import StrEnum

DOMAIN = "proxmoxve"
PROXMOX_CLIENTS = "proxmox_clients"
CONF_REALM = "realm"
CONF_NODE = "node"
CONF_NODES = "nodes"
CONF_VMS = "vms"
CONF_CONTAINERS = "containers"

COORDINATORS = "coordinators"

DEFAULT_PORT = 8006
DEFAULT_REALM = "pam"
DEFAULT_VERIFY_SSL = True
TYPE_VM = 0
TYPE_CONTAINER = 1
UPDATE_INTERVAL = 60

LOGGER = logging.getLogger(__package__)


class ProxmoxType(StrEnum):
    """Proxmox type of information."""

    QEMU = "qemu"
    LXC = "lxc"


class ProxmoxKeyAPIParse(StrEnum):
    """Proxmox key of data API parse."""

    STATUS = "status"
    NAME = "name"
