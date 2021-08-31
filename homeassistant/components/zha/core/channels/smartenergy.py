"""Smart energy channels module for Zigbee Home Automation."""
from __future__ import annotations

from collections.abc import Coroutine

from zigpy.zcl.clusters import smartenergy

from homeassistant.const import (
    POWER_WATT,
    TIME_HOURS,
    TIME_SECONDS,
    VOLUME_FLOW_RATE_CUBIC_FEET_PER_MINUTE,
    VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR,
)
from homeassistant.core import callback

from .. import registries, typing as zha_typing
from ..const import REPORT_CONFIG_DEFAULT
from .base import ZigbeeChannel


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.Calendar.cluster_id)
class Calendar(ZigbeeChannel):
    """Calendar channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.DeviceManagement.cluster_id)
class DeviceManagement(ZigbeeChannel):
    """Device Management channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.Drlc.cluster_id)
class Drlc(ZigbeeChannel):
    """Demand Response and Load Control channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.EnergyManagement.cluster_id)
class EnergyManagement(ZigbeeChannel):
    """Energy Management channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.Events.cluster_id)
class Events(ZigbeeChannel):
    """Event channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.KeyEstablishment.cluster_id)
class KeyEstablishment(ZigbeeChannel):
    """Key Establishment channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.MduPairing.cluster_id)
class MduPairing(ZigbeeChannel):
    """Pairing channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.Messaging.cluster_id)
class Messaging(ZigbeeChannel):
    """Messaging channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.Metering.cluster_id)
class Metering(ZigbeeChannel):
    """Metering channel."""

    REPORT_CONFIG = [{"attr": "instantaneous_demand", "config": REPORT_CONFIG_DEFAULT}]

    unit_of_measure_map = {
        0x00: POWER_WATT,
        0x01: VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR,
        0x02: VOLUME_FLOW_RATE_CUBIC_FEET_PER_MINUTE,
        0x03: f"ccf/{TIME_HOURS}",
        0x04: f"US gal/{TIME_HOURS}",
        0x05: f"IMP gal/{TIME_HOURS}",
        0x06: f"BTU/{TIME_HOURS}",
        0x07: f"l/{TIME_HOURS}",
        0x08: "kPa",
        0x09: "kPa",
        0x0A: f"mcf/{TIME_HOURS}",
        0x0B: "unitless",
        0x0C: f"MJ/{TIME_SECONDS}",
    }

    def __init__(
        self, cluster: zha_typing.ZigpyClusterType, ch_pool: zha_typing.ChannelPoolType
    ) -> None:
        """Initialize Metering."""
        super().__init__(cluster, ch_pool)
        self._format_spec = None

    @property
    def divisor(self) -> int:
        """Return divisor for the value."""
        return self.cluster.get("divisor") or 1

    @property
    def multiplier(self) -> int:
        """Return multiplier for the value."""
        return self.cluster.get("multiplier") or 1

    def async_configure_channel_specific(self) -> Coroutine:
        """Configure channel."""
        return self.fetch_config(False)

    def async_initialize_channel_specific(self, from_cache: bool) -> Coroutine:
        """Initialize channel."""
        return self.fetch_config(True)

    @callback
    def attribute_updated(self, attrid: int, value: int) -> None:
        """Handle attribute update from Metering cluster."""
        if None in (self.multiplier, self.divisor, self._format_spec):
            return
        super().attribute_updated(attrid, value)

    @property
    def unit_of_measurement(self) -> str:
        """Return unit of measurement."""
        uom = self.cluster.get("unit_of_measure", 0x7F)
        return self.unit_of_measure_map.get(uom & 0x7F, "unknown")

    async def fetch_config(self, from_cache: bool) -> None:
        """Fetch config from device and updates format specifier."""
        results = await self.get_attributes(
            ["divisor", "multiplier", "unit_of_measure", "demand_formatting"],
            from_cache=from_cache,
        )

        fmting = results.get(
            "demand_formatting", 0xF9
        )  # 1 digit to the right, 15 digits to the left

        r_digits = int(fmting & 0x07)  # digits to the right of decimal point
        l_digits = (fmting >> 3) & 0x0F  # digits to the left of decimal point
        if l_digits == 0:
            l_digits = 15
        width = r_digits + l_digits + (1 if r_digits > 0 else 0)

        if fmting & 0x80:
            self._format_spec = "{:" + str(width) + "." + str(r_digits) + "f}"
        else:
            self._format_spec = "{:0" + str(width) + "." + str(r_digits) + "f}"

    def formatter_function(self, value: int) -> int | float:
        """Return formatted value for display."""
        value = value * self.multiplier / self.divisor
        if self.unit_of_measurement == POWER_WATT:
            # Zigbee spec power unit is kW, but we show the value in W
            value_watt = value * 1000
            if value_watt < 100:
                return round(value_watt, 1)
            return round(value_watt)
        return self._format_spec.format(value).lstrip()


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.Prepayment.cluster_id)
class Prepayment(ZigbeeChannel):
    """Prepayment channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.Price.cluster_id)
class Price(ZigbeeChannel):
    """Price channel."""


@registries.ZIGBEE_CHANNEL_REGISTRY.register(smartenergy.Tunneling.cluster_id)
class Tunneling(ZigbeeChannel):
    """Tunneling channel."""
