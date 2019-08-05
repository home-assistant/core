"""
Lightlink channels module for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import logging

import zigpy.zcl.clusters.lightlink as lightlink

from . import ZIGBEE_CHANNEL_REGISTRY, ZigbeeChannel

_LOGGER = logging.getLogger(__name__)


@ZIGBEE_CHANNEL_REGISTRY.register(lightlink.LightLink.cluster_id)
class LightLink(ZigbeeChannel):
    """Lightlink channel."""

    pass
