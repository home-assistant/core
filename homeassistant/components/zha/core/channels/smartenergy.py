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


@registries.ZIGBEE_CHANNEL_REGISTRY.register
class Calendar(ZigbeeChannel):
    """Calendar channel."""

    CLUSTER_ID = smartenergy.Calendar.cluster_id
    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register
class DeviceManagement(ZigbeeChannel):
    """Device Management channel."""

    CLUSTER_ID = smartenergy.DeviceManagement.cluster_id
    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register
class Drlc(ZigbeeChannel):
    """Demand Response and Load Control channel."""

    CLUSTER_ID = smartenergy.Drlc.cluster_id
    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register
class EnergyManagement(ZigbeeChannel):
    """Energy Management channel."""

    CLUSTER_ID = smartenergy.EnergyManagement.cluster_id
    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register
class Events(ZigbeeChannel):
    """Event channel."""

    CLUSTER_ID = smartenergy.Events.cluster_id
    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register
class KeyEstablishment(ZigbeeChannel):
    """Key Establishment channel."""

    CLUSTER_ID = smartenergy.KeyEstablishment.cluster_id
    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register
class MduPairing(ZigbeeChannel):
    """Pairing channel."""

    CLUSTER_ID = smartenergy.MduPairing.cluster_id
    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register
class Messaging(ZigbeeChannel):
    """Messaging channel."""

    CLUSTER_ID = smartenergy.Messaging.cluster_id
    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register
class Metering(AttributeListeningChannel):
    """Metering channel."""

    CLUSTER_ID = smartenergy.Metering.cluster_id
    REPORT_CONFIG = [{"attr": "instantaneous_demand", "config": REPORT_CONFIG_DEFAULT}]


@registries.ZIGBEE_CHANNEL_REGISTRY.register
class Prepayment(ZigbeeChannel):
    """Prepayment channel."""

    CLUSTER_ID = smartenergy.Prepayment.cluster_id
    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register
class Price(ZigbeeChannel):
    """Price channel."""

    CLUSTER_ID = smartenergy.Price.cluster_id
    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register
class Tunneling(ZigbeeChannel):
    """Tunneling channel."""

    CLUSTER_ID = smartenergy.Tunneling.cluster_id
    pass
