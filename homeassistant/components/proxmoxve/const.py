"""Constants for ProxmoxVE."""

from enum import StrEnum
import logging

DOMAIN = "proxmoxve"
PROXMOX_CLIENTS = "proxmox_clients"
CONF_REALM = "realm"
CONF_NODE = "node"
CONF_NODES = "nodes"
CONF_VMS = "vms"
CONF_CONTAINERS = "containers"
SERVICE_SET_VM_STATUS = "set_vm_status"
ATTR_STATUS_COMMAND = "status_command"

COORDINATORS = "coordinators"

DEFAULT_PORT = 8006
DEFAULT_REALM = "pam"
DEFAULT_VERIFY_SSL = True
TYPE_VM = 0
TYPE_CONTAINER = 1
UPDATE_INTERVAL = 60

_LOGGER = logging.getLogger(__package__)


class StatusCommand(StrEnum):
    """Status command for setting status for vms."""

    # Reboot the VM by shutting it down, and starting it again.
    REBOOT = "reboot"

    # Reset virtual machine.
    RESET = "reset"

    # Resume virtual machine.
    RESUME = "resume"

    # Shutdown virtual machine. This is similar to pressing the power button on a physical machine.
    SHUTDOWN = "shutdown"

    # Start virtual machine.
    START = "start"

    # Stop virtual machine. The qemu process will exit immediately.
    STOP = "stop"

    # Suspend virtual machine.
    SUSPEND = "suspend"
