"""
Lightlink channels module for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import logging

import zigpy.zcl.clusters.lightlink as lightlink

from . import ZigbeeChannel
from .. import registries

_LOGGER = logging.getLogger(__name__)


@registries.ZIGBEE_CHANNEL_REGISTRY.register
class LightLink(ZigbeeChannel):
    """Lightlink channel."""

    CLUSTER_ID = lightlink.LightLink.cluster_id
    pass
