"""ONVIF models."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from homeassistant.const import EntityCategory


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
    video_source_token: str | None = None


@dataclass
class Capabilities:
    """Represents Service capabilities."""

    snapshot: bool = False
    events: bool = False
    ptz: bool = False
    imaging: bool = False


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


class PullPointManagerState(Enum):
    """States for the pullpoint manager."""

    STOPPED = 0  # Not running or not supported
    STARTED = 1  # Running and renewing
    PAUSED = 2  # Switched to webhook, but can resume
    FAILED = 3  # Failed to do initial subscription


class WebHookManagerState(Enum):
    """States for the webhook manager."""

    STOPPED = 0
    STARTED = 1
    FAILED = 2  # Failed to do initial subscription
