"""Home automation channels module for Zigbee Home Automation."""
from __future__ import annotations

from collections.abc import Coroutine

import zigpy.zcl.clusters.homeautomation as homeautomation

from .. import registries
from ..const import (
    CHANNEL_ELECTRICAL_MEASUREMENT,
    REPORT_CONFIG_DEFAULT,
    SIGNAL_ATTR_UPDATED,
)
from .base import ZigbeeChannel


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    homeautomation.ApplianceEventAlerts.cluster_id
)
class ApplianceEventAlerts(ZigbeeChannel):
    """Appliance Event Alerts channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    homeautomation.ApplianceIdentification.cluster_id
)
class ApplianceIdentification(ZigbeeChannel):
    """Appliance Identification channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    homeautomation.ApplianceStatistics.cluster_id
)
class ApplianceStatistics(ZigbeeChannel):
    """Appliance Statistics channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(homeautomation.Diagnostic.cluster_id)
class Diagnostic(ZigbeeChannel):
    """Diagnostic channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    homeautomation.ElectricalMeasurement.cluster_id
)
class ElectricalMeasurementChannel(ZigbeeChannel):
    """Channel that polls active power level."""

    CHANNEL_NAME = CHANNEL_ELECTRICAL_MEASUREMENT

    REPORT_CONFIG = ({"attr": "active_power", "config": REPORT_CONFIG_DEFAULT},)

    async def async_update(self):
        """Retrieve latest state."""
        self.debug("async_update")

        # This is a polling channel. Don't allow cache.
        result = await self.get_attribute_value("active_power", from_cache=False)
        if result is not None:
            self.async_send_signal(
                f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}",
                0x050B,
                "active_power",
                result,
            )

    def async_initialize_channel_specific(self, from_cache: bool) -> Coroutine:
        """Initialize channel specific attributes."""

        return self.get_attributes(
            [
                "ac_power_divisor",
                "power_divisor",
                "ac_power_multiplier",
                "power_multiplier",
            ],
            from_cache=True,
        )

    @property
    def divisor(self) -> int | None:
        """Return active power divisor."""
        return self.cluster.get(
            "ac_power_divisor", self.cluster.get("power_divisor", 1)
        )

    @property
    def multiplier(self) -> int | None:
        """Return active power divisor."""
        return self.cluster.get(
            "ac_power_multiplier", self.cluster.get("power_multiplier", 1)
        )


@registries.ZIGBEE_CHANNEL_REGISTRY.register(
    homeautomation.MeterIdentification.cluster_id
)
class MeterIdentification(ZigbeeChannel):
    """Metering Identification channel."""
