"""Protocol cluster handlers module for Zigbee Home Automation."""
from zigpy.zcl.clusters.protocol import (
    AnalogInputExtended,
    AnalogInputRegular,
    AnalogOutputExtended,
    AnalogOutputRegular,
    AnalogValueExtended,
    AnalogValueRegular,
    BacnetProtocolTunnel,
    BinaryInputExtended,
    BinaryInputRegular,
    BinaryOutputExtended,
    BinaryOutputRegular,
    BinaryValueExtended,
    BinaryValueRegular,
    GenericTunnel,
    MultistateInputExtended,
    MultistateInputRegular,
    MultistateOutputExtended,
    MultistateOutputRegular,
    MultistateValueExtended,
    MultistateValueRegular,
)

from .. import registries
from . import ClusterHandler


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(AnalogInputExtended.cluster_id)
class AnalogInputExtendedClusterHandler(ClusterHandler):
    """Analog Input Extended cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(AnalogInputRegular.cluster_id)
class AnalogInputRegularClusterHandler(ClusterHandler):
    """Analog Input Regular cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(AnalogOutputExtended.cluster_id)
class AnalogOutputExtendedClusterHandler(ClusterHandler):
    """Analog Output Regular cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(AnalogOutputRegular.cluster_id)
class AnalogOutputRegularClusterHandler(ClusterHandler):
    """Analog Output Regular cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(AnalogValueExtended.cluster_id)
class AnalogValueExtendedClusterHandler(ClusterHandler):
    """Analog Value Extended edition cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(AnalogValueRegular.cluster_id)
class AnalogValueRegularClusterHandler(ClusterHandler):
    """Analog Value Regular cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(BacnetProtocolTunnel.cluster_id)
class BacnetProtocolTunnelClusterHandler(ClusterHandler):
    """Bacnet Protocol Tunnel cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(BinaryInputExtended.cluster_id)
class BinaryInputExtendedClusterHandler(ClusterHandler):
    """Binary Input Extended cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(BinaryInputRegular.cluster_id)
class BinaryInputRegularClusterHandler(ClusterHandler):
    """Binary Input Regular cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(BinaryOutputExtended.cluster_id)
class BinaryOutputExtendedClusterHandler(ClusterHandler):
    """Binary Output Extended cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(BinaryOutputRegular.cluster_id)
class BinaryOutputRegularClusterHandler(ClusterHandler):
    """Binary Output Regular cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(BinaryValueExtended.cluster_id)
class BinaryValueExtendedClusterHandler(ClusterHandler):
    """Binary Value Extended cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(BinaryValueRegular.cluster_id)
class BinaryValueRegularClusterHandler(ClusterHandler):
    """Binary Value Regular cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(GenericTunnel.cluster_id)
class GenericTunnelClusterHandler(ClusterHandler):
    """Generic Tunnel cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(MultistateInputExtended.cluster_id)
class MultiStateInputExtendedClusterHandler(ClusterHandler):
    """Multistate Input Extended cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(MultistateInputRegular.cluster_id)
class MultiStateInputRegularClusterHandler(ClusterHandler):
    """Multistate Input Regular cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    MultistateOutputExtended.cluster_id
)
class MultiStateOutputExtendedClusterHandler(ClusterHandler):
    """Multistate Output Extended cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(MultistateOutputRegular.cluster_id)
class MultiStateOutputRegularClusterHandler(ClusterHandler):
    """Multistate Output Regular cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(MultistateValueExtended.cluster_id)
class MultiStateValueExtendedClusterHandler(ClusterHandler):
    """Multistate Value Extended cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(MultistateValueRegular.cluster_id)
class MultiStateValueRegularClusterHandler(ClusterHandler):
    """Multistate Value Regular cluster handler."""
