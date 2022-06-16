"""Typing helpers for ZHA component."""
from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar

import zigpy.device
import zigpy.endpoint
import zigpy.group
import zigpy.zcl
import zigpy.zdo

# pylint: disable=invalid-name
CALLABLE_T = TypeVar("CALLABLE_T", bound=Callable)
ChannelsType = "Channels"
ChannelPoolType = "ChannelPool"
ClientChannelType = "ClientChannel"
ZDOChannelType = "ZDOChannel"
ZhaEntityType = "ZHAEntity"
ZhaGatewayType = "ZHAGateway"
ZhaGroupType = "ZHAGroupType"
ZigpyClusterType = zigpy.zcl.Cluster
ZigpyDeviceType = zigpy.device.Device
ZigpyEndpointType = zigpy.endpoint.Endpoint
ZigpyGroupType = zigpy.group.Group
ZigpyZdoType = zigpy.zdo.ZDO

if TYPE_CHECKING:
    import homeassistant.components.zha.entity

    from . import channels, gateway, group
    from .channels import base as base_channels

    ChannelsType = channels.Channels
    ChannelPoolType = channels.ChannelPool
    ClientChannelType = base_channels.ClientChannel
    ZDOChannelType = base_channels.ZDOChannel
    ZhaEntityType = homeassistant.components.zha.entity.ZhaEntity
    ZhaGatewayType = gateway.ZHAGateway
    ZhaGroupType = group.ZHAGroup
