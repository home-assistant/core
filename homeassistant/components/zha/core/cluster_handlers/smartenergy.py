"""Smart energy cluster handlers module for Zigbee Home Automation."""
from __future__ import annotations

import enum
from functools import partialmethod
from typing import TYPE_CHECKING

import zigpy.zcl
from zigpy.zcl.clusters.smartenergy import (
    Calendar,
    DeviceManagement,
    Drlc,
    EnergyManagement,
    Events,
    KeyEstablishment,
    MduPairing,
    Messaging,
    Metering,
    Prepayment,
    Price,
    Tunneling,
)

from .. import registries
from ..const import (
    REPORT_CONFIG_ASAP,
    REPORT_CONFIG_DEFAULT,
    REPORT_CONFIG_OP,
    SIGNAL_ATTR_UPDATED,
)
from . import AttrReportConfig, ClusterHandler

if TYPE_CHECKING:
    from ..endpoint import Endpoint


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(Calendar.cluster_id)
class CalendarClusterHandler(ClusterHandler):
    """Calendar cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(DeviceManagement.cluster_id)
class DeviceManagementClusterHandler(ClusterHandler):
    """Device Management cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(Drlc.cluster_id)
class DrlcClusterHandler(ClusterHandler):
    """Demand Response and Load Control cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(EnergyManagement.cluster_id)
class EnergyManagementClusterHandler(ClusterHandler):
    """Energy Management cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(Events.cluster_id)
class EventsClusterHandler(ClusterHandler):
    """Event cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(KeyEstablishment.cluster_id)
class KeyEstablishmentClusterHandler(ClusterHandler):
    """Key Establishment cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(MduPairing.cluster_id)
class MduPairingClusterHandler(ClusterHandler):
    """Pairing cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(Messaging.cluster_id)
class MessagingClusterHandler(ClusterHandler):
    """Messaging cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(Metering.cluster_id)
class MeteringClusterHandler(ClusterHandler):
    """Metering cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=Metering.AttributeDefs.instantaneous_demand.name,
            config=REPORT_CONFIG_OP,
        ),
        AttrReportConfig(
            attr=Metering.AttributeDefs.current_summ_delivered.name,
            config=REPORT_CONFIG_DEFAULT,
        ),
        AttrReportConfig(
            attr=Metering.AttributeDefs.current_tier1_summ_delivered.name,
            config=REPORT_CONFIG_DEFAULT,
        ),
        AttrReportConfig(
            attr=Metering.AttributeDefs.current_tier2_summ_delivered.name,
            config=REPORT_CONFIG_DEFAULT,
        ),
        AttrReportConfig(
            attr=Metering.AttributeDefs.current_tier3_summ_delivered.name,
            config=REPORT_CONFIG_DEFAULT,
        ),
        AttrReportConfig(
            attr=Metering.AttributeDefs.current_tier4_summ_delivered.name,
            config=REPORT_CONFIG_DEFAULT,
        ),
        AttrReportConfig(
            attr=Metering.AttributeDefs.current_tier5_summ_delivered.name,
            config=REPORT_CONFIG_DEFAULT,
        ),
        AttrReportConfig(
            attr=Metering.AttributeDefs.current_tier6_summ_delivered.name,
            config=REPORT_CONFIG_DEFAULT,
        ),
        AttrReportConfig(
            attr=Metering.AttributeDefs.current_summ_received.name,
            config=REPORT_CONFIG_DEFAULT,
        ),
        AttrReportConfig(
            attr=Metering.AttributeDefs.status.name,
            config=REPORT_CONFIG_ASAP,
        ),
    )
    ZCL_INIT_ATTRS = {
        Metering.AttributeDefs.demand_formatting.name: True,
        Metering.AttributeDefs.divisor.name: True,
        Metering.AttributeDefs.metering_device_type.name: True,
        Metering.AttributeDefs.multiplier.name: True,
        Metering.AttributeDefs.summation_formatting.name: True,
        Metering.AttributeDefs.unit_of_measure.name: True,
    }

    METERING_DEVICE_TYPES_ELECTRIC = {
        0,
        7,
        8,
        9,
        10,
        11,
        13,
        14,
        15,
        127,
        134,
        135,
        136,
        137,
        138,
        140,
        141,
        142,
    }
    METERING_DEVICE_TYPES_GAS = {1, 128}
    METERING_DEVICE_TYPES_WATER = {2, 129}
    METERING_DEVICE_TYPES_HEATING_COOLING = {3, 5, 6, 130, 132, 133}

    metering_device_type = {
        0: "Electric Metering",
        1: "Gas Metering",
        2: "Water Metering",
        3: "Thermal Metering",  # deprecated
        4: "Pressure Metering",
        5: "Heat Metering",
        6: "Cooling Metering",
        7: "End Use Measurement Device (EUMD) for metering electric vehicle charging",
        8: "PV Generation Metering",
        9: "Wind Turbine Generation Metering",
        10: "Water Turbine Generation Metering",
        11: "Micro Generation Metering",
        12: "Solar Hot Water Generation Metering",
        13: "Electric Metering Element/Phase 1",
        14: "Electric Metering Element/Phase 2",
        15: "Electric Metering Element/Phase 3",
        127: "Mirrored Electric Metering",
        128: "Mirrored Gas Metering",
        129: "Mirrored Water Metering",
        130: "Mirrored Thermal Metering",  # deprecated
        131: "Mirrored Pressure Metering",
        132: "Mirrored Heat Metering",
        133: "Mirrored Cooling Metering",
        134: "Mirrored End Use Measurement Device (EUMD) for metering electric vehicle charging",
        135: "Mirrored PV Generation Metering",
        136: "Mirrored Wind Turbine Generation Metering",
        137: "Mirrored Water Turbine Generation Metering",
        138: "Mirrored Micro Generation Metering",
        139: "Mirrored Solar Hot Water Generation Metering",
        140: "Mirrored Electric Metering Element/Phase 1",
        141: "Mirrored Electric Metering Element/Phase 2",
        142: "Mirrored Electric Metering Element/Phase 3",
    }

    class DeviceStatusElectric(enum.IntFlag):
        """Electric Metering Device Status."""

        NO_ALARMS = 0
        CHECK_METER = 1
        LOW_BATTERY = 2
        TAMPER_DETECT = 4
        POWER_FAILURE = 8
        POWER_QUALITY = 16
        LEAK_DETECT = 32  # Really?
        SERVICE_DISCONNECT = 64
        RESERVED = 128

    class DeviceStatusGas(enum.IntFlag):
        """Gas Metering Device Status."""

        NO_ALARMS = 0
        CHECK_METER = 1
        LOW_BATTERY = 2
        TAMPER_DETECT = 4
        NOT_DEFINED = 8
        LOW_PRESSURE = 16
        LEAK_DETECT = 32
        SERVICE_DISCONNECT = 64
        REVERSE_FLOW = 128

    class DeviceStatusWater(enum.IntFlag):
        """Water Metering Device Status."""

        NO_ALARMS = 0
        CHECK_METER = 1
        LOW_BATTERY = 2
        TAMPER_DETECT = 4
        PIPE_EMPTY = 8
        LOW_PRESSURE = 16
        LEAK_DETECT = 32
        SERVICE_DISCONNECT = 64
        REVERSE_FLOW = 128

    class DeviceStatusHeatingCooling(enum.IntFlag):
        """Heating and Cooling Metering Device Status."""

        NO_ALARMS = 0
        CHECK_METER = 1
        LOW_BATTERY = 2
        TAMPER_DETECT = 4
        TEMPERATURE_SENSOR = 8
        BURST_DETECT = 16
        LEAK_DETECT = 32
        SERVICE_DISCONNECT = 64
        REVERSE_FLOW = 128

    class DeviceStatusDefault(enum.IntFlag):
        """Metering Device Status."""

        NO_ALARMS = 0

    class FormatSelector(enum.IntEnum):
        """Format specified selector."""

        DEMAND = 0
        SUMMATION = 1

    def __init__(self, cluster: zigpy.zcl.Cluster, endpoint: Endpoint) -> None:
        """Initialize Metering."""
        super().__init__(cluster, endpoint)
        self._format_spec: str | None = None
        self._summa_format: str | None = None

    @property
    def divisor(self) -> int:
        """Return divisor for the value."""
        return self.cluster.get(Metering.AttributeDefs.divisor.name) or 1

    @property
    def device_type(self) -> str | int | None:
        """Return metering device type."""
        dev_type = self.cluster.get(Metering.AttributeDefs.metering_device_type.name)
        if dev_type is None:
            return None
        return self.metering_device_type.get(dev_type, dev_type)

    @property
    def multiplier(self) -> int:
        """Return multiplier for the value."""
        return self.cluster.get(Metering.AttributeDefs.multiplier.name) or 1

    @property
    def status(self) -> int | None:
        """Return metering device status."""
        if (status := self.cluster.get(Metering.AttributeDefs.status.name)) is None:
            return None

        metering_device_type = self.cluster.get(
            Metering.AttributeDefs.metering_device_type.name
        )
        if metering_device_type in self.METERING_DEVICE_TYPES_ELECTRIC:
            return self.DeviceStatusElectric(status)
        if metering_device_type in self.METERING_DEVICE_TYPES_GAS:
            return self.DeviceStatusGas(status)
        if metering_device_type in self.METERING_DEVICE_TYPES_WATER:
            return self.DeviceStatusWater(status)
        if metering_device_type in self.METERING_DEVICE_TYPES_HEATING_COOLING:
            return self.DeviceStatusHeatingCooling(status)
        return self.DeviceStatusDefault(status)

    @property
    def unit_of_measurement(self) -> int:
        """Return unit of measurement."""
        return self.cluster.get(Metering.AttributeDefs.unit_of_measure.name)

    async def async_initialize_cluster_handler_specific(self, from_cache: bool) -> None:
        """Fetch config from device and updates format specifier."""

        fmting = self.cluster.get(
            Metering.AttributeDefs.demand_formatting.name, 0xF9
        )  # 1 digit to the right, 15 digits to the left
        self._format_spec = self.get_formatting(fmting)

        fmting = self.cluster.get(
            Metering.AttributeDefs.summation_formatting.name, 0xF9
        )  # 1 digit to the right, 15 digits to the left
        self._summa_format = self.get_formatting(fmting)

    async def async_update(self) -> None:
        """Retrieve latest state."""
        self.debug("async_update")

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

    @staticmethod
    def get_formatting(formatting: int) -> str:
        """Return a formatting string, given the formatting value.

        Bits 0 to 2: Number of Digits to the right of the Decimal Point.
        Bits 3 to 6: Number of Digits to the left of the Decimal Point.
        Bit 7: If set, suppress leading zeros.
        """
        r_digits = int(formatting & 0x07)  # digits to the right of decimal point
        l_digits = (formatting >> 3) & 0x0F  # digits to the left of decimal point
        if l_digits == 0:
            l_digits = 15
        width = r_digits + l_digits + (1 if r_digits > 0 else 0)

        if formatting & 0x80:
            # suppress leading 0
            return f"{{:{width}.{r_digits}f}}"

        return f"{{:0{width}.{r_digits}f}}"

    def _formatter_function(
        self, selector: FormatSelector, value: int
    ) -> int | float | str:
        """Return formatted value for display."""
        value_float = value * self.multiplier / self.divisor
        if self.unit_of_measurement == 0:
            # Zigbee spec power unit is kW, but we show the value in W
            value_watt = value_float * 1000
            if value_watt < 100:
                return round(value_watt, 1)
            return round(value_watt)
        if selector == self.FormatSelector.SUMMATION:
            assert self._summa_format
            return self._summa_format.format(value_float).lstrip()
        assert self._format_spec
        return self._format_spec.format(value_float).lstrip()

    demand_formatter = partialmethod(_formatter_function, FormatSelector.DEMAND)
    summa_formatter = partialmethod(_formatter_function, FormatSelector.SUMMATION)


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(Prepayment.cluster_id)
class PrepaymentClusterHandler(ClusterHandler):
    """Prepayment cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(Price.cluster_id)
class PriceClusterHandler(ClusterHandler):
    """Price cluster handler."""


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(Tunneling.cluster_id)
class TunnelingClusterHandler(ClusterHandler):
    """Tunneling cluster handler."""
