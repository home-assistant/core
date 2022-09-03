"""Constants for ProxmoxVE."""
from homeassistant.backports.enum import StrEnum

DOMAIN = "proxmoxve"

CONF_REALM = "realm"

PLATFORMS = ["binary_sensor"]
PROXMOX_CLIENTS = "proxmox_clients"
PROXMOX_CLIENT = "proxmox_client"

DEFAULT_PORT = 8006
DEFAULT_REALM = "pve"
DEFAULT_VERIFY_SSL = False

COORDINATORS = "coordinators"
API_DATA = "api_data"


class ProxmoxType(StrEnum):
    """Proxmox type of information."""

    Proxmox = "proxmox"
    Node = "node"
    QEMU = "qemu"
    LXC = "lxc"


TYPE_VM = 0
TYPE_CONTAINER = 1
UPDATE_INTERVAL = 60

CONF_NODE = "node"
CONF_NODES = "nodes"
CONF_VMS = "vms"
CONF_CONTAINERS = "containers"
CONF_QEMU = "qemu"
CONF_LXC = "lxc"
ID = "vmid"
