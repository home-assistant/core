"""Constants for Proxmox VE."""

DOMAIN = "proxmoxve"
ATTRIBUTION = "Data provided by Proxmox VE"
PROXMOX_CLIENTS = "proxmox_clients"
CONF_REALM = "realm"
CONF_NODE = "node"
CONF_NODES = "nodes"
CONF_VMS = "vms"
CONF_CONTAINERS = "containers"
PLATFORMS = ["binary_sensor", "sensor"]

DEFAULT_PORT = 8006
DEFAULT_REALM = "pam"
DEFAULT_VERIFY_SSL = True

GUESTTYPE_QEMU = "qemu"
GUESTTYPE_LXC = "lxc"
GUESTTYPE_ALL = [GUESTTYPE_QEMU, GUESTTYPE_LXC]
