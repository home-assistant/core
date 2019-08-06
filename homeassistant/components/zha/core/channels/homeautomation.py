"""
Home automation channels module for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import logging

import zigpy.zcl.clusters.homeautomation as homeautomation

from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import ZIGBEE_CHANNEL_REGISTRY, AttributeListeningChannel, ZigbeeChannel
from ..const import (
    CHANNEL_ELECTRICAL_MEASUREMENT,
    REPORT_CONFIG_DEFAULT,
    SIGNAL_ATTR_UPDATED,
)

_LOGGER = logging.getLogger(__name__)


@ZIGBEE_CHANNEL_REGISTRY.register
class ApplianceEventAlerts(ZigbeeChannel):
    """Appliance Event Alerts channel."""

    CLUSTER_ID = homeautomation.ApplianceEventAlerts.cluster_id
    pass


@ZIGBEE_CHANNEL_REGISTRY.register
class ApplianceIdentification(ZigbeeChannel):
    """Appliance Identification channel."""

    CLUSTER_ID = homeautomation.ApplianceIdentification.cluster_id
    pass


@ZIGBEE_CHANNEL_REGISTRY.register
class ApplianceStatistics(ZigbeeChannel):
    """Appliance Statistics channel."""

    CLUSTER_ID = homeautomation.ApplianceStatistics.cluster_id
    pass


@ZIGBEE_CHANNEL_REGISTRY.register
class Diagnostic(ZigbeeChannel):
    """Diagnostic channel."""

    CLUSTER_ID = homeautomation.Diagnostic.cluster_id
    pass


@ZIGBEE_CHANNEL_REGISTRY.register
class ElectricalMeasurementChannel(AttributeListeningChannel):
    """Channel that polls active power level."""

    CHANNEL_NAME = CHANNEL_ELECTRICAL_MEASUREMENT
    CLUSTER_ID = homeautomation.ElectricalMeasurement.cluster_id
    REPORT_CONFIG = ({"attr": "active_power", "config": REPORT_CONFIG_DEFAULT},)

    async def async_update(self):
        """Retrieve latest state."""
        self.debug("async_update")

        # This is a polling channel. Don't allow cache.
        result = await self.get_attribute_value("active_power", from_cache=False)
        async_dispatcher_send(
            self._zha_device.hass,
            "{}_{}".format(self.unique_id, SIGNAL_ATTR_UPDATED),
            result,
        )

    async def async_initialize(self, from_cache):
        """Initialize channel."""
        await self.get_attribute_value("active_power", from_cache=from_cache)
        await super().async_initialize(from_cache)


@ZIGBEE_CHANNEL_REGISTRY.register
class MeterIdentification(ZigbeeChannel):
    """Metering Identification channel."""

    CLUSTER_ID = homeautomation.MeterIdentification.cluster_id
    pass
