"""
Smart energy channels module for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import logging

import zigpy.zcl.clusters.smartenergy as smartenergy

from .. import registries
from ..channels import AttributeListeningChannel, ZigbeeChannel
from ..const import REPORT_CONFIG_DEFAULT

_LOGGER = logging.getLogger(__name__)


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.Calendar.cluster_id)
class Calendar(ZigbeeChannel):
    """Calendar channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.DeviceManagement.cluster_id)
class DeviceManagement(ZigbeeChannel):
    """Device Management channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.Drlc.cluster_id)
class Drlc(ZigbeeChannel):
    """Demand Response and Load Control channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.EnergyManagement.cluster_id)
class EnergyManagement(ZigbeeChannel):
    """Energy Management channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.Events.cluster_id)
class Events(ZigbeeChannel):
    """Event channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.KeyEstablishment.cluster_id)
class KeyEstablishment(ZigbeeChannel):
    """Key Establishment channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.MduPairing.cluster_id)
class MduPairing(ZigbeeChannel):
    """Pairing channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.Messaging.cluster_id)
class Messaging(ZigbeeChannel):
    """Messaging channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.Metering.cluster_id)
class Metering(AttributeListeningChannel):
    """Metering channel."""

    REPORT_CONFIG = [{"attr": "instantaneous_demand", "config": REPORT_CONFIG_DEFAULT}]


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.Prepayment.cluster_id)
class Prepayment(ZigbeeChannel):
    """Prepayment channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.Price.cluster_id)
class Price(ZigbeeChannel):
    """Price channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.Tunneling.cluster_id)
class Tunneling(ZigbeeChannel):
    """Tunneling channel."""

    pass
