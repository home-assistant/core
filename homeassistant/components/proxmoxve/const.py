"""Constants for ProxmoxVE."""

import logging

from homeassistant.backports.enum import StrEnum

DOMAIN = "proxmoxve"
INTEGRATION_NAME = "Proxmox VE"

LOGGER = logging.getLogger(__package__)

CONF_CONTAINERS = "containers"
CONF_LXC = "lxc"
CONF_NODE = "node"
CONF_NODES = "nodes"
CONF_QEMU = "qemu"
CONF_REALM = "realm"
CONF_VMS = "vms"

CONF_SCAN_INTERVAL_HOST = "interval_update_host"
CONF_SCAN_INTERVAL_NODE = "interval_update_node"
CONF_SCAN_INTERVAL_QEMU = "interval_update_qemu"
CONF_SCAN_INTERVAL_LXC = "interval_update_lxc"

UPDATE_INTERVAL_DEFAULT = 60

DEFAULT_PORT = 8006
DEFAULT_REALM = "pam"
DEFAULT_VERIFY_SSL = True

ID = "vmid"
COORDINATORS = "coordinators"
PROXMOX_CLIENT = "proxmox_client"


class ProxmoxType(StrEnum):
    """Proxmox type of information."""

    Proxmox = "proxmox"
    Node = "node"
    QEMU = "qemu"
    LXC = "lxc"


class ProxmoxKeyAPIParse(StrEnum):
    """Proxmox key of data API parse."""

    VERSION = "version"
    STATUS = "status"
    UPTIME = "uptime"
    MODEL = "model"
    CPU = "cpu"
    MEMORY_USED = "memory_used"
    MEMORY_TOTAL = "memory_total"
    MEMORY_FREE = "memory_free"
    SWAP_TOTAL = "swap_total"
    SWAP_FREE = "swap_free"
    DISK_USED = "disk_used"
    DISK_TOTAL = "disk_total"
    HEALTH = "health"
    NAME = "name"
    NETWORK_IN = "network_in"
    NETWORK_OUT = "network_out"
    CPU_NODE = "cpu_node"
    DISK = "disk"
    MAX_DISK = "maxdisk"
    SWAP = "swap"
    MEMORY = "memory"
    CPU_INFO = "cpuinfo"
    USED = "used"
    TOTAL = "total"
    FREE = "free"
    FREE_MEM = "freemem"
    MAX_MEM = "maxmem"
    MEM = "mem"
    QMP_STATUS = "qmpstatus"
    NET_IN = "netin"
    NET_OUT = "netout"
