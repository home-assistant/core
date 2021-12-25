"""Type definitions for Proxmox integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.sensor import SensorEntityDescription


@dataclass
class ProxmoxBinarySensorDescription(BinarySensorEntityDescription):
    """Class describing Proxmox binarysensor entities."""

    unit_metric: str | None = None
    unit_imperial: str | None = None


@dataclass
class ProxmoxSensorDescription(SensorEntityDescription):
    """Class describing Proxmox sensor entities."""

    unit_metric: str | None = None
    unit_imperial: str | None = None
    conversion: Callable | None = None  # conversion factor to be applied to units
    calculation: Callable | None = None  # calculation
