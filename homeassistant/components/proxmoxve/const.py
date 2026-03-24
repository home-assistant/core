"""Constants for ProxmoxVE."""

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

NODE_ONLINE = "online"
VM_CONTAINER_RUNNING = "running"

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

PERM_POWER = "VM.PowerMgmt"
