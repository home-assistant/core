"""
Lightlink channels module for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/integrations/zha/
"""
import logging

import zigpy.zcl.clusters.lightlink as lightlink

from . import ZigbeeChannel
from .. import registries

_LOGGER = logging.getLogger(__name__)


@registries.CHANNEL_ONLY_CLUSTERS.register(lightlink.LightLink.cluster_id)
@registries.ZIGBEE_CHANNEL_REGISTRY.register(lightlink.LightLink.cluster_id)
class LightLink(ZigbeeChannel):
    """Lightlink channel."""

    pass
