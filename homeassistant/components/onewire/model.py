"""Type definitions for 1-Wire integration."""
from __future__ import annotations

from dataclasses import dataclass

from pi1wire import OneWireInterface

from homeassistant.helpers.entity import DeviceInfo


@dataclass
class OWDeviceDescription:
    """OWDeviceDescription device description class."""

    device_info: DeviceInfo


@dataclass
class OWDirectDeviceDescription(OWDeviceDescription):
    """SysBus device description class."""

    interface: OneWireInterface


@dataclass
class OWServerDeviceDescription(OWDeviceDescription):
    """OWServer device description class."""

    family: str
    id: str
    path: str
    type: str
