"""Constants for ProxmoxVE."""

from enum import StrEnum


class ResourceType(StrEnum):
    """Proxmox resource types that support snapshots."""

    VM = "vm"
    CONTAINER = "container"


DOMAIN = "proxmoxve"
CONF_REALM = "realm"
CONF_NODE = "node"
CONF_NODES = "nodes"
CONF_VMS = "vms"
CONF_CONTAINERS = "containers"

SERVICE_CREATE_SNAPSHOT = "create_snapshot"

NODE_ONLINE = "online"
VM_CONTAINER_RUNNING = "running"


DEFAULT_PORT = 8006
DEFAULT_REALM = "pam"
DEFAULT_VERIFY_SSL = True
TYPE_VM = 0
TYPE_CONTAINER = 1
UPDATE_INTERVAL = 60

PERM_POWER = "VM.PowerMgmt"
