"""Lighting channels module for Zigbee Home Automation."""
from __future__ import annotations

from contextlib import suppress

from zigpy.zcl.clusters import lighting

from .. import registries
from ..const import REPORT_CONFIG_DEFAULT
from .base import AttrReportConfig, ClientChannel, ZigbeeChannel


@registries.ZIGBEE_CHANNEL_REGISTRY.register(lighting.Ballast.cluster_id)
class Ballast(ZigbeeChannel):
    """Ballast channel."""


@registries.CLIENT_CHANNELS_REGISTRY.register(lighting.Color.cluster_id)
class ColorClientChannel(ClientChannel):
    """Color client channel."""


@registries.BINDABLE_CLUSTERS.register(lighting.Color.cluster_id)
@registries.ZIGBEE_CHANNEL_REGISTRY.register(lighting.Color.cluster_id)
class ColorChannel(ZigbeeChannel):
    """Color channel."""

    CAPABILITIES_COLOR_XY = 0x08
    CAPABILITIES_COLOR_TEMP = 0x10
    UNSUPPORTED_ATTRIBUTE = 0x86
    REPORT_CONFIG = (
        AttrReportConfig(attr="current_x", config=REPORT_CONFIG_DEFAULT),
        AttrReportConfig(attr="current_y", config=REPORT_CONFIG_DEFAULT),
        AttrReportConfig(attr="color_temperature", config=REPORT_CONFIG_DEFAULT),
    )
    MAX_MIREDS: int = 500
    MIN_MIREDS: int = 153
    ZCL_INIT_ATTRS = {
        "color_mode": False,
        "color_temp_physical_min": True,
        "color_temp_physical_max": True,
        "color_capabilities": True,
        "color_loop_active": False,
    }

    @property
    def color_capabilities(self) -> int:
        """Return color capabilities of the light."""
        with suppress(KeyError):
            return self.cluster["color_capabilities"]
        if self.cluster.get("color_temperature") is not None:
            return self.CAPABILITIES_COLOR_XY | self.CAPABILITIES_COLOR_TEMP
        return self.CAPABILITIES_COLOR_XY

    @property
    def color_mode(self) -> int | None:
        """Return cached value of the color_mode attribute."""
        return self.cluster.get("color_mode")

    @property
    def color_loop_active(self) -> int | None:
        """Return cached value of the color_loop_active attribute."""
        return self.cluster.get("color_loop_active")

    @property
    def color_temperature(self) -> int | None:
        """Return cached value of color temperature."""
        return self.cluster.get("color_temperature")

    @property
    def current_x(self) -> int | None:
        """Return cached value of the current_x attribute."""
        return self.cluster.get("current_x")

    @property
    def current_y(self) -> int | None:
        """Return cached value of the current_y attribute."""
        return self.cluster.get("current_y")

    @property
    def min_mireds(self) -> int:
        """Return the coldest color_temp that this channel supports."""
        return self.cluster.get("color_temp_physical_min", self.MIN_MIREDS)

    @property
    def max_mireds(self) -> int:
        """Return the warmest color_temp that this channel supports."""
        return self.cluster.get("color_temp_physical_max", self.MAX_MIREDS)
