"""Protocol channels module for Zigbee Home Automation."""
from zigpy.zcl.clusters import protocol

from .. import registries
from .base import ZigbeeChannel


@registries.ZIGBEE_CHANNEL_REGISTRY.register(protocol.AnalogInputExtended.cluster_id)
class AnalogInputExtended(ZigbeeChannel):
    """Analog Input Extended channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(protocol.AnalogInputRegular.cluster_id)
class AnalogInputRegular(ZigbeeChannel):
    """Analog Input Regular channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(protocol.AnalogOutputExtended.cluster_id)
class AnalogOutputExtended(ZigbeeChannel):
    """Analog Output Regular channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(protocol.AnalogOutputRegular.cluster_id)
class AnalogOutputRegular(ZigbeeChannel):
    """Analog Output Regular channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(protocol.AnalogValueExtended.cluster_id)
class AnalogValueExtended(ZigbeeChannel):
    """Analog Value Extended edition channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(protocol.AnalogValueRegular.cluster_id)
class AnalogValueRegular(ZigbeeChannel):
    """Analog Value Regular channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(protocol.BacnetProtocolTunnel.cluster_id)
class BacnetProtocolTunnel(ZigbeeChannel):
    """Bacnet Protocol Tunnel channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(protocol.BinaryInputExtended.cluster_id)
class BinaryInputExtended(ZigbeeChannel):
    """Binary Input Extended channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(protocol.BinaryInputRegular.cluster_id)
class BinaryInputRegular(ZigbeeChannel):
    """Binary Input Regular channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(protocol.BinaryOutputExtended.cluster_id)
class BinaryOutputExtended(ZigbeeChannel):
    """Binary Output Extended channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(protocol.BinaryOutputRegular.cluster_id)
class BinaryOutputRegular(ZigbeeChannel):
    """Binary Output Regular channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(protocol.BinaryValueExtended.cluster_id)
class BinaryValueExtended(ZigbeeChannel):
    """Binary Value Extended channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(protocol.BinaryValueRegular.cluster_id)
class BinaryValueRegular(ZigbeeChannel):
    """Binary Value Regular channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(protocol.GenericTunnel.cluster_id)
class GenericTunnel(ZigbeeChannel):
    """Generic Tunnel channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    protocol.MultistateInputExtended.cluster_id
)
class MultiStateInputExtended(ZigbeeChannel):
    """Multistate Input Extended channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(protocol.MultistateInputRegular.cluster_id)
class MultiStateInputRegular(ZigbeeChannel):
    """Multistate Input Regular channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    protocol.MultistateOutputExtended.cluster_id
)
class MultiStateOutputExtended(ZigbeeChannel):
    """Multistate Output Extended channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    protocol.MultistateOutputRegular.cluster_id
)
class MultiStateOutputRegular(ZigbeeChannel):
    """Multistate Output Regular channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    protocol.MultistateValueExtended.cluster_id
)
class MultiStateValueExtended(ZigbeeChannel):
    """Multistate Value Extended channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(protocol.MultistateValueRegular.cluster_id)
class MultiStateValueRegular(ZigbeeChannel):
    """Multistate Value Regular channel."""
