"""Lightlink channels module for Zigbee Home Automation."""
import logging

import zigpy.zcl.clusters.lightlink as lightlink

from .. import registries
from .base import ZigbeeChannel

_LOGGER = logging.getLogger(__name__)


@registries.CHANNEL_ONLY_CLUSTERS.register(lightlink.LightLink.cluster_id)
@registries.ZIGBEE_CHANNEL_REGISTRY.register(lightlink.LightLink.cluster_id)
class LightLink(ZigbeeChannel):
    """Lightlink channel."""
