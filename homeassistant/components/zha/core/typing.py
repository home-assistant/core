"""Typing helpers for ZHA component."""

from typing import TYPE_CHECKING, Callable, Tuple, TypedDict, TypeVar

import zigpy.device
import zigpy.endpoint
import zigpy.group
import zigpy.types.named
import zigpy.zcl
import zigpy.zdo
import zigpy.zdo.types

# pylint: disable=invalid-name
CALLABLE_T = TypeVar("CALLABLE_T", bound=Callable)
ChannelType = "ZigbeeChannel"
ChannelsType = "Channels"
ChannelPoolType = "ChannelPool"
EventRelayChannelType = "EventRelayChannel"
ZDOChannelType = "ZDOChannel"
ZhaDeviceType = "ZHADevice"
ZhaEntityType = "ZHAEntity"
ZhaGatewayType = "ZHAGateway"
ZhaGroupType = "ZHAGroup"
ReportConfigType = Tuple[int, int, int]


class AttributeReportConfig(TypedDict):
    """Attribute reporting configuration."""

    attr: str
    config: ReportConfigType


AttributeReportConfigType = Tuple[AttributeReportConfig, ...]
ZigpyClusterType = zigpy.zcl.Cluster
ZigpyDeviceType = zigpy.device.Device
ZigpyEndpointType = zigpy.endpoint.Endpoint
ZigpyGroupType = zigpy.group.Group
ZigpyZdoType = zigpy.zdo.ZDO
ZigpyEUI64Type = zigpy.types.named.EUI64
ZigpyZDOCommandType = zigpy.zdo.types.ZDOCmd
ZigpyNodeDescriptorType = zigpy.zdo.types.NodeDescriptor

if TYPE_CHECKING:
    import homeassistant.components.zha.core.channels as channels
    import homeassistant.components.zha.core.channels.base as base_channels
    import homeassistant.components.zha.core.device
    import homeassistant.components.zha.core.gateway
    import homeassistant.components.zha.entity
    import homeassistant.components.zha.core.channels
    import homeassistant.components.zha.core.group

    ChannelType = base_channels.ZigbeeChannel
    ChannelsType = channels.Channels
    ChannelPoolType = channels.ChannelPool
    EventRelayChannelType = base_channels.EventRelayChannel
    ZDOChannelType = base_channels.ZDOChannel
    ZhaDeviceType = homeassistant.components.zha.core.device.ZHADevice
    ZhaEntityType = homeassistant.components.zha.entity.ZhaEntity
    ZhaGatewayType = homeassistant.components.zha.core.gateway.ZHAGateway
    ZhaGroupType = homeassistant.components.zha.core.group.ZHAGroup
