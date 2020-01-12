"""
Home automation channels module for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/integrations/zha/
"""
import logging
from typing import Optional

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

    def __init__(self, cluster, device):
        """Initialize Metering."""
        super().__init__(cluster, device)
        self._divisor = None
        self._multiplier = None

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
        await self.fetch_config(from_cache)
        await super().async_initialize(from_cache)

    async def fetch_config(self, from_cache):
        """Fetch config from device and updates format specifier."""
        divisor = await self.get_attribute_value(
            "ac_power_divisor", from_cache=from_cache
        )
        if divisor is None:
            divisor = await self.get_attribute_value(
                "power_divisor", from_cache=from_cache
            )
        self._divisor = divisor

        mult = await self.get_attribute_value(
            "ac_power_multiplier", from_cache=from_cache
        )
        if mult is None:
            mult = await self.get_attribute_value(
                "power_multiplier", from_cache=from_cache
            )
        self._multiplier = mult

    @property
    def divisor(self) -> Optional[int]:
        """Return active power divisor."""
        return self._divisor or 1

    @property
    def multiplier(self) -> Optional[int]:
        """Return active power divisor."""
        return self._multiplier or 1


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    homeautomation.MeterIdentification.cluster_id
)
class MeterIdentification(ZigbeeChannel):
    """Metering Identification channel."""

    pass
