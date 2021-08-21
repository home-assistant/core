"""Type definitions for 1-Wire integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from homeassistant.helpers.entity import EntityDescription


@dataclass
class OneWireEntityDescription(EntityDescription):
    """Class describing OneWire entities."""

    device_file: str| None = None
    device_id: str| None = None
    type: str| None = None


class DeviceComponentDescription(TypedDict, total=False):
    """Device component description class."""

    path: str
    name: str
    type: str
    default_disabled: bool


class OWServerDeviceDescription(TypedDict):
    """OWServer device description class."""

    path: str
    family: str
    type: str
