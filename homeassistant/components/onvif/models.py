"""ONVIF models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.helpers.entity import EntityCategory


@dataclass
class DeviceInfo:
    """Represent device information."""

    manufacturer: str | None = None
    model: str | None = None
    fw_version: str | None = None
    serial_number: str | None = None
    mac: str | None = None


@dataclass
class Resolution:
    """Represent video resolution."""

    width: int
    height: int


@dataclass
class Video:
    """Represent video encoding settings."""

    encoding: str
    resolution: Resolution


@dataclass
class PTZ:
    """Represents PTZ configuration on a profile."""

    continuous: bool
    relative: bool
    absolute: bool
    presets: list[str] | None = None


@dataclass
class Profile:
    """Represent a ONVIF Profile."""

    index: int
    token: str
    name: str
    video: Video
    ptz: PTZ | None = None


@dataclass
class Capabilities:
    """Represents Service capabilities."""

    snapshot: bool = False
    events: bool = False
    ptz: bool = False


@dataclass
class Event:
    """Represents a ONVIF event."""

    uid: str
    name: str
    platform: str
    device_class: str | None = None
    unit_of_measurement: str | None = None
    value: Any = None
    entity_category: EntityCategory | None = None
    entity_enabled: bool = True
