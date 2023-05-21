"""Protocol cluster handlers module for Zigbee Home Automation."""
from zigpy.zcl.clusters import protocol

from . import ClusterHandler
from .. import registries


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    protocol.AnalogInputExtended.cluster_id
)
class AnalogInputExtended(ClusterHandler):
    """Analog Input Extended cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    protocol.AnalogInputRegular.cluster_id
)
class AnalogInputRegular(ClusterHandler):
    """Analog Input Regular cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    protocol.AnalogOutputExtended.cluster_id
)
class AnalogOutputExtended(ClusterHandler):
    """Analog Output Regular cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    protocol.AnalogOutputRegular.cluster_id
)
class AnalogOutputRegular(ClusterHandler):
    """Analog Output Regular cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    protocol.AnalogValueExtended.cluster_id
)
class AnalogValueExtended(ClusterHandler):
    """Analog Value Extended edition cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    protocol.AnalogValueRegular.cluster_id
)
class AnalogValueRegular(ClusterHandler):
    """Analog Value Regular cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    protocol.BacnetProtocolTunnel.cluster_id
)
class BacnetProtocolTunnel(ClusterHandler):
    """Bacnet Protocol Tunnel cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    protocol.BinaryInputExtended.cluster_id
)
class BinaryInputExtended(ClusterHandler):
    """Binary Input Extended cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    protocol.BinaryInputRegular.cluster_id
)
class BinaryInputRegular(ClusterHandler):
    """Binary Input Regular cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    protocol.BinaryOutputExtended.cluster_id
)
class BinaryOutputExtended(ClusterHandler):
    """Binary Output Extended cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    protocol.BinaryOutputRegular.cluster_id
)
class BinaryOutputRegular(ClusterHandler):
    """Binary Output Regular cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    protocol.BinaryValueExtended.cluster_id
)
class BinaryValueExtended(ClusterHandler):
    """Binary Value Extended cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    protocol.BinaryValueRegular.cluster_id
)
class BinaryValueRegular(ClusterHandler):
    """Binary Value Regular cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(protocol.GenericTunnel.cluster_id)
class GenericTunnel(ClusterHandler):
    """Generic Tunnel cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    protocol.MultistateInputExtended.cluster_id
)
class MultiStateInputExtended(ClusterHandler):
    """Multistate Input Extended cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    protocol.MultistateInputRegular.cluster_id
)
class MultiStateInputRegular(ClusterHandler):
    """Multistate Input Regular cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    protocol.MultistateOutputExtended.cluster_id
)
class MultiStateOutputExtended(ClusterHandler):
    """Multistate Output Extended cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    protocol.MultistateOutputRegular.cluster_id
)
class MultiStateOutputRegular(ClusterHandler):
    """Multistate Output Regular cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    protocol.MultistateValueExtended.cluster_id
)
class MultiStateValueExtended(ClusterHandler):
    """Multistate Value Extended cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    protocol.MultistateValueRegular.cluster_id
)
class MultiStateValueRegular(ClusterHandler):
    """Multistate Value Regular cluster handler."""
