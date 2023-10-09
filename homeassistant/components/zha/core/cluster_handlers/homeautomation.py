"""Home automation cluster handlers module for Zigbee Home Automation."""
from __future__ import annotations

import enum

from zigpy.zcl.clusters import homeautomation

from .. import registries
from ..const import (
    CLUSTER_HANDLER_ELECTRICAL_MEASUREMENT,
    REPORT_CONFIG_DEFAULT,
    REPORT_CONFIG_OP,
    SIGNAL_ATTR_UPDATED,
)
from . import AttrReportConfig, ClusterHandler


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    homeautomation.ApplianceEventAlerts.cluster_id
)
class ApplianceEventAlerts(ClusterHandler):
    """Appliance Event Alerts cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    homeautomation.ApplianceIdentification.cluster_id
)
class ApplianceIdentification(ClusterHandler):
    """Appliance Identification cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    homeautomation.ApplianceStatistics.cluster_id
)
class ApplianceStatistics(ClusterHandler):
    """Appliance Statistics cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    homeautomation.Diagnostic.cluster_id
)
class Diagnostic(ClusterHandler):
    """Diagnostic cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    homeautomation.ElectricalMeasurement.cluster_id
)
class ElectricalMeasurementClusterHandler(ClusterHandler):
    """Cluster handler that polls active power level."""

    CLUSTER_HANDLER_NAME = CLUSTER_HANDLER_ELECTRICAL_MEASUREMENT

    class MeasurementType(enum.IntFlag):
        """Measurement types."""

        ACTIVE_MEASUREMENT = 1
        REACTIVE_MEASUREMENT = 2
        APPARENT_MEASUREMENT = 4
        PHASE_A_MEASUREMENT = 8
        PHASE_B_MEASUREMENT = 16
        PHASE_C_MEASUREMENT = 32
        DC_MEASUREMENT = 64
        HARMONICS_MEASUREMENT = 128
        POWER_QUALITY_MEASUREMENT = 256

    REPORT_CONFIG = (
        AttrReportConfig(attr="active_power", config=REPORT_CONFIG_OP),
        AttrReportConfig(attr="active_power_max", config=REPORT_CONFIG_DEFAULT),
        AttrReportConfig(attr="apparent_power", config=REPORT_CONFIG_OP),
        AttrReportConfig(attr="rms_current", config=REPORT_CONFIG_OP),
        AttrReportConfig(attr="rms_current_max", config=REPORT_CONFIG_DEFAULT),
        AttrReportConfig(attr="rms_voltage", config=REPORT_CONFIG_OP),
        AttrReportConfig(attr="rms_voltage_max", config=REPORT_CONFIG_DEFAULT),
        AttrReportConfig(attr="ac_frequency", config=REPORT_CONFIG_OP),
        AttrReportConfig(attr="ac_frequency_max", config=REPORT_CONFIG_DEFAULT),
    )
    ZCL_INIT_ATTRS = {
        "ac_current_divisor": True,
        "ac_current_multiplier": True,
        "ac_power_divisor": True,
        "ac_power_multiplier": True,
        "ac_voltage_divisor": True,
        "ac_voltage_multiplier": True,
        "ac_frequency_divisor": True,
        "ac_frequency_multiplier": True,
        "measurement_type": True,
        "power_divisor": True,
        "power_multiplier": True,
    }

    async def async_update(self):
        """Retrieve latest state."""
        self.debug("async_update")

        # This is a polling cluster handler. Don't allow cache.
        attrs = [
            a["attr"]
            for a in self.REPORT_CONFIG
            if a["attr"] not in self.cluster.unsupported_attributes
        ]
        result = await self.get_attributes(attrs, from_cache=False, only_cache=False)
        if result:
            for attr, value in result.items():
                self.async_send_signal(
                    f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}",
                    self.cluster.find_attribute(attr).id,
                    attr,
                    value,
                )

    @property
    def ac_current_divisor(self) -> int:
        """Return ac current divisor."""
        return self.cluster.get("ac_current_divisor") or 1

    @property
    def ac_current_multiplier(self) -> int:
        """Return ac current multiplier."""
        return self.cluster.get("ac_current_multiplier") or 1

    @property
    def ac_voltage_divisor(self) -> int:
        """Return ac voltage divisor."""
        return self.cluster.get("ac_voltage_divisor") or 1

    @property
    def ac_voltage_multiplier(self) -> int:
        """Return ac voltage multiplier."""
        return self.cluster.get("ac_voltage_multiplier") or 1

    @property
    def ac_frequency_divisor(self) -> int:
        """Return ac frequency divisor."""
        return self.cluster.get("ac_frequency_divisor") or 1

    @property
    def ac_frequency_multiplier(self) -> int:
        """Return ac frequency multiplier."""
        return self.cluster.get("ac_frequency_multiplier") or 1

    @property
    def ac_power_divisor(self) -> int:
        """Return active power divisor."""
        return self.cluster.get(
            "ac_power_divisor", self.cluster.get("power_divisor") or 1
        )

    @property
    def ac_power_multiplier(self) -> int:
        """Return active power divisor."""
        return self.cluster.get(
            "ac_power_multiplier", self.cluster.get("power_multiplier") or 1
        )

    @property
    def measurement_type(self) -> str | None:
        """Return Measurement type."""
        if (meas_type := self.cluster.get("measurement_type")) is None:
            return None

        meas_type = self.MeasurementType(meas_type)
        return ", ".join(
            m.name
            for m in self.MeasurementType
            if m in meas_type and m.name is not None
        )


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(
    homeautomation.MeterIdentification.cluster_id
)
class MeterIdentification(ClusterHandler):
    """Metering Identification cluster handler."""
