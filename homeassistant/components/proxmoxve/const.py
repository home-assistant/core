"""Constants for ProxmoxVE."""

from enum import StrEnum

DOMAIN = "proxmoxve"
CONF_AUTH_METHOD = "auth_method"
CONF_REALM = "realm"
CONF_NODE = "node"
CONF_NODES = "nodes"
CONF_TOKEN = "token"
CONF_TOKEN_ID = "token_id"
CONF_TOKEN_SECRET = "token_value"
CONF_VMS = "vms"
CONF_CONTAINERS = "containers"

CONF_USER = "user"

NODE_ONLINE = "online"
VM_CONTAINER_RUNNING = "running"

STORAGE_ACTIVE = 1
STORAGE_SHARED = 1
STORAGE_ENABLED = 1
STATUS_OK = "ok"

AUTH_PAM = "pam"
AUTH_PVE = "pve"
AUTH_OTHER = "other"
AUTH_METHODS = [AUTH_PAM, AUTH_PVE, AUTH_OTHER]

DEFAULT_PORT = 8006
DEFAULT_REALM = AUTH_PAM
DEFAULT_VERIFY_SSL = True
TYPE_VM = 0
TYPE_CONTAINER = 1
UPDATE_INTERVAL = 60


class ProxmoxPermission(StrEnum):
    """Proxmox permissions."""

    POWER = "VM.PowerMgmt"
    SNAPSHOT = "VM.Snapshot"
