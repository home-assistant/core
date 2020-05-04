"""ONVIF models."""
from typing import List

import attr


@attr.s
class DeviceInfo:
    """Represent device information."""

    manufacturer = attr.ib(type=str, default=None)
    model = attr.ib(type=str, default=None)
    fw_version = attr.ib(type=str, default=None)
    mac = attr.ib(type=str, default=None)


@attr.s
class Resolution:
    """Represent video resolution."""

    width = attr.ib(type=int)
    height = attr.ib(type=int)


@attr.s
class Video:
    """Represent video encoding settings."""

    encoding = attr.ib(type=str)
    resolution = attr.ib(type=Resolution)


@attr.s
class PTZ:
    """Represents PTZ configuration on a profile."""

    continuous = attr.ib(type=bool)
    relative = attr.ib(type=bool)
    absolute = attr.ib(type=bool)
    presets = attr.ib(type=List[str], default=None)


@attr.s
class Profile:
    """Represent a ONVIF Profile."""

    index = attr.ib(type=int)
    token = attr.ib(type=str)
    name = attr.ib(type=str)
    video = attr.ib(type=Video)
    ptz = attr.ib(type=PTZ, default=None)


@attr.s
class Capabilities:
    """Represents Service capabilities."""

    snapshot = attr.ib(type=bool, default=False)
    ptz = attr.ib(type=bool, default=False)
