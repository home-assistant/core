"""ONVIF models."""
from dataclasses import dataclass
from typing import List


@dataclass
class DeviceInfo:
    """Represent device information."""

    manufacturer: str = None
    model: str = None
    fw_version: str = None
    mac: str = None


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
    presets: List[str] = None


@dataclass
class Profile:
    """Represent a ONVIF Profile."""

    index: int
    token: str
    name: str
    video: Video
    ptz: PTZ = None


@dataclass
class Capabilities:
    """Represents Service capabilities."""

    snapshot: bool = False
    ptz: bool = False
