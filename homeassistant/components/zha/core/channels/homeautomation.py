"""
Home automation channels module for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import logging

import zigpy.zcl.clusters.homeautomation as homeautomation

from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import AttributeListeningChannel, ZigbeeChannel
from .. import registries
from ..const import (
    CHANNEL_ELECTRICAL_MEASUREMENT,
    REPORT_CONFIG_DEFAULT,
    SIGNAL_ATTR_UPDATED,
)

_LOGGER = logging.getLogger(__name__)


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    homeautomation.ApplianceEventAlerts.cluster_id
)
class ApplianceEventAlerts(ZigbeeChannel):
    """Appliance Event Alerts channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    homeautomation.ApplianceIdentification.cluster_id
)
class ApplianceIdentification(ZigbeeChannel):
    """Appliance Identification channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    homeautomation.ApplianceStatistics.cluster_id
)
class ApplianceStatistics(ZigbeeChannel):
    """Appliance Statistics channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(homeautomation.Diagnostic.cluster_id)
class Diagnostic(ZigbeeChannel):
    """Diagnostic channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    homeautomation.ElectricalMeasurement.cluster_id
)
class ElectricalMeasurementChannel(AttributeListeningChannel):
    """Channel that polls active power level."""

    CHANNEL_NAME = CHANNEL_ELECTRICAL_MEASUREMENT

    REPORT_CONFIG = ({"attr": "active_power", "config": REPORT_CONFIG_DEFAULT},)

    async def async_update(self):
        """Retrieve latest state."""
        self.debug("async_update")

        # This is a polling channel. Don't allow cache.
        result = await self.get_attribute_value("active_power", from_cache=False)
        async_dispatcher_send(
            self._zha_device.hass, f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}", result
        )

    async def async_initialize(self, from_cache):
        """Initialize channel."""
        await self.get_attribute_value("active_power", from_cache=from_cache)
        await super().async_initialize(from_cache)


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    homeautomation.MeterIdentification.cluster_id
)
class MeterIdentification(ZigbeeChannel):
    """Metering Identification channel."""

    pass
