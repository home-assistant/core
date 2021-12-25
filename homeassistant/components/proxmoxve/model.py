"""Type definitions for Proxmox integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import BinarySensorEntityDescription


@dataclass
class ProxmoxBinarySensorDescription(BinarySensorEntityDescription):
    """Class describing Proxmox binarysensor entities."""

    unit_metric: str | None = None
    unit_imperial: str | None = None
