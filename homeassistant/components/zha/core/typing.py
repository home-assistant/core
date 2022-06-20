"""Typing helpers for ZHA component."""
from collections.abc import Callable
from typing import TypeVar

import zigpy.device
import zigpy.endpoint
import zigpy.group
import zigpy.zdo

# pylint: disable=invalid-name
CALLABLE_T = TypeVar("CALLABLE_T", bound=Callable)
ZigpyDeviceType = zigpy.device.Device
ZigpyEndpointType = zigpy.endpoint.Endpoint
ZigpyGroupType = zigpy.group.Group
ZigpyZdoType = zigpy.zdo.ZDO
