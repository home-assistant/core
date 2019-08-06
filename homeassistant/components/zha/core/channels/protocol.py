"""
Protocol channels module for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import logging

import zigpy.zcl.clusters.protocol as protocol

from ..channels import ZIGBEE_CHANNEL_REGISTRY, ZigbeeChannel

_LOGGER = logging.getLogger(__name__)


@ZIGBEE_CHANNEL_REGISTRY.register
class AnalogInputExtended(ZigbeeChannel):
    """Analog Input Extended channel."""

    CLUSTER_ID = protocol.AnalogInputExtended.cluster_id
    pass


@ZIGBEE_CHANNEL_REGISTRY.register
class AnalogInputRegular(ZigbeeChannel):
    """Analog Input Regular channel."""

    CLUSTER_ID = protocol.AnalogInputRegular.cluster_id
    pass


@ZIGBEE_CHANNEL_REGISTRY.register
class AnalogOutputExtended(ZigbeeChannel):
    """Analog Output Regular channel."""

    CLUSTER_ID = protocol.AnalogOutputExtended.cluster_id
    pass


@ZIGBEE_CHANNEL_REGISTRY.register
class AnalogOutputRegular(ZigbeeChannel):
    """Analog Output Regular channel."""

    CLUSTER_ID = protocol.AnalogOutputRegular.cluster_id
    pass


@ZIGBEE_CHANNEL_REGISTRY.register
class AnalogValueExtended(ZigbeeChannel):
    """Analog Value Extended edition channel."""

    CLUSTER_ID = protocol.AnalogValueExtended.cluster_id
    pass


@ZIGBEE_CHANNEL_REGISTRY.register
class AnalogValueRegular(ZigbeeChannel):
    """Analog Value Regular channel."""

    CLUSTER_ID = protocol.AnalogValueRegular.cluster_id
    pass


@ZIGBEE_CHANNEL_REGISTRY.register
class BacnetProtocolTunnel(ZigbeeChannel):
    """Bacnet Protocol Tunnel channel."""

    CLUSTER_ID = protocol.BacnetProtocolTunnel.cluster_id
    pass


@ZIGBEE_CHANNEL_REGISTRY.register
class BinaryInputExtended(ZigbeeChannel):
    """Binary Input Extended channel."""

    CLUSTER_ID = protocol.BinaryInputExtended.cluster_id
    pass


@ZIGBEE_CHANNEL_REGISTRY.register
class BinaryInputRegular(ZigbeeChannel):
    """Binary Input Regular channel."""

    CLUSTER_ID = protocol.BinaryInputRegular.cluster_id
    pass


@ZIGBEE_CHANNEL_REGISTRY.register
class BinaryOutputExtended(ZigbeeChannel):
    """Binary Output Extended channel."""

    CLUSTER_ID = protocol.BinaryOutputExtended.cluster_id
    pass


@ZIGBEE_CHANNEL_REGISTRY.register
class BinaryOutputRegular(ZigbeeChannel):
    """Binary Output Regular channel."""

    CLUSTER_ID = protocol.BinaryOutputRegular.cluster_id
    pass


@ZIGBEE_CHANNEL_REGISTRY.register
class BinaryValueExtended(ZigbeeChannel):
    """Binary Value Extended channel."""

    CLUSTER_ID = protocol.BinaryValueExtended.cluster_id
    pass


@ZIGBEE_CHANNEL_REGISTRY.register
class BinaryValueRegular(ZigbeeChannel):
    """Binary Value Regular channel."""

    CLUSTER_ID = protocol.BinaryValueRegular.cluster_id
    pass


@ZIGBEE_CHANNEL_REGISTRY.register
class GenericTunnel(ZigbeeChannel):
    """Generic Tunnel channel."""

    CLUSTER_ID = protocol.GenericTunnel.cluster_id
    pass


@ZIGBEE_CHANNEL_REGISTRY.register
class MultiStateInputExtended(ZigbeeChannel):
    """Multistate Input Extended channel."""

    CLUSTER_ID = protocol.MultistateInputExtended.cluster_id
    pass


@ZIGBEE_CHANNEL_REGISTRY.register
class MultiStateInputRegular(ZigbeeChannel):
    """Multistate Input Regular channel."""

    CLUSTER_ID = protocol.MultistateInputRegular.cluster_id
    pass


@ZIGBEE_CHANNEL_REGISTRY.register
class MultiStateOutputExtended(ZigbeeChannel):
    """Multistate Output Extended channel."""

    CLUSTER_ID = protocol.MultistateOutputExtended.cluster_id
    pass


@ZIGBEE_CHANNEL_REGISTRY.register
class MultiStateOutputRegular(ZigbeeChannel):
    """Multistate Output Regular channel."""

    CLUSTER_ID = protocol.MultistateOutputRegular.cluster_id
    pass


@ZIGBEE_CHANNEL_REGISTRY.register
class MultiStateValueExtended(ZigbeeChannel):
    """Multistate Value Extended channel."""

    CLUSTER_ID = protocol.MultistateValueExtended.cluster_id
    pass


@ZIGBEE_CHANNEL_REGISTRY.register
class MultiStateValueRegular(ZigbeeChannel):
    """Multistate Value Regular channel."""

    CLUSTER_ID = protocol.MultistateValueRegular.cluster_id
    pass
