"""Constants for Proxmox integration."""
from __future__ import annotations

from datetime import timedelta
from enum import Enum
from typing import Final

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import ATTR_TIME

from .model import ProxmoxBinarySensorDescription, ProxmoxSensorDescription


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

PROXMOX_SENSOR_TYPES: Final[tuple[ProxmoxSensorDescription, ...]] = (
    ProxmoxSensorDescription(
        key="uptime",
        icon="mdi:database-clock-outline",
        unit_metric=ATTR_TIME,
        unit_imperial=ATTR_TIME,
        conversion=lambda x: timedelta(seconds=x),
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


PARSE_DATA = [
    sensor.key for sensor in PROXMOX_SENSOR_TYPES + PROXMOX_BINARYSENSOR_TYPES
] + ["name"]
PROXMOX_SENSOR_TYPES_ALL = PROXMOX_SENSOR_TYPES
