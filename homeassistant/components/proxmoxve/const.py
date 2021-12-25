"""Constants for Proxmox integration."""
from __future__ import annotations

from enum import Enum
from typing import Final

from .model import ProxmoxBinarySensorDescription


class Node_Type(Enum):
    """Defines Node Types as VM or Containers."""

    TYPE_VM = 0
    TYPE_CONTAINER = 1


DOMAIN = "proxmoxve"
PROXMOX_CLIENTS = "proxmox_clients"
COORDINATORS = "coordinators"

CONF_REALM = "realm"
CONF_NODE = "node"
CONF_NODES = "nodes"
CONF_VMS = "vms"
CONF_CONTAINERS = "containers"

DEFAULT_PORT = 8006
DEFAULT_REALM = "pam"
DEFAULT_VERIFY_SSL = True
DEFAULT_SCAN_INTERVAL = 60


PROXMOX_BINARYSENSOR_TYPES: Final[tuple[ProxmoxBinarySensorDescription, ...]] = (
    ProxmoxBinarySensorDescription(
        key="status",
        icon="mdi:server",
    ),
)
