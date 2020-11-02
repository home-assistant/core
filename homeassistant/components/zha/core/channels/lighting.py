"""Lighting channels module for Zigbee Home Automation."""
from typing import Optional

import zigpy.zcl.clusters.lighting as lighting

from .. import registries, typing as zha_typing
from ..const import REPORT_CONFIG_DEFAULT
from .base import ClientChannel, ZigbeeChannel


@registries.ZIGBEE_CHANNEL_REGISTRY.register(lighting.Ballast.cluster_id)
class Ballast(ZigbeeChannel):
    """Ballast channel."""


@registries.CLIENT_CHANNELS_REGISTRY.register(lighting.Color.cluster_id)
class ColorClientChannel(ClientChannel):
    """Color client channel."""


@registries.BINDABLE_CLUSTERS.register(lighting.Color.cluster_id)
@registries.LIGHT_CLUSTERS.register(lighting.Color.cluster_id)
@registries.ZIGBEE_CHANNEL_REGISTRY.register(lighting.Color.cluster_id)
class ColorChannel(ZigbeeChannel):
    """Color channel."""

    CAPABILITIES_COLOR_XY = 0x08
    CAPABILITIES_COLOR_TEMP = 0x10
    UNSUPPORTED_ATTRIBUTE = 0x86
    REPORT_CONFIG = (
        {"attr": "current_x", "config": REPORT_CONFIG_DEFAULT},
        {"attr": "current_y", "config": REPORT_CONFIG_DEFAULT},
        {"attr": "color_temperature", "config": REPORT_CONFIG_DEFAULT},
    )

    def __init__(
        self, cluster: zha_typing.ZigpyClusterType, ch_pool: zha_typing.ChannelPoolType
    ) -> None:
        """Initialize ColorChannel."""
        super().__init__(cluster, ch_pool)
        self._color_capabilities = None
        self._min_mireds = 153
        self._max_mireds = 500

    @property
    def color_loop_active(self) -> Optional[int]:
        """Return cached value of the color_loop_active attribute."""
        return self.cluster.get("color_loop_active")

    @property
    def color_temperature(self) -> Optional[int]:
        """Return cached value of color temperature."""
        return self.cluster.get("color_temperature")

    @property
    def current_x(self) -> Optional[int]:
        """Return cached value of the current_x attribute."""
        return self.cluster.get("current_x")

    @property
    def current_y(self) -> Optional[int]:
        """Return cached value of the current_y attribute."""
        return self.cluster.get("current_y")

    @property
    def min_mireds(self) -> int:
        """Return the coldest color_temp that this channel supports."""
        return self.cluster.get("color_temp_physical_min", self._min_mireds)

    @property
    def max_mireds(self) -> int:
        """Return the warmest color_temp that this channel supports."""
        return self.cluster.get("color_temp_physical_max", self._max_mireds)

    def get_color_capabilities(self):
        """Return the color capabilities."""
        return self._color_capabilities

    async def async_configure(self):
        """Configure channel."""
        await self.fetch_color_capabilities(False)
        await super().async_configure()

    async def async_initialize(self, from_cache):
        """Initialize channel."""
        await self.fetch_color_capabilities(True)
        attributes = ["color_temperature", "current_x", "current_y"]
        await self.get_attributes(attributes, from_cache=from_cache)

    async def fetch_color_capabilities(self, from_cache):
        """Get the color configuration."""
        attributes = [
            "color_temp_physical_min",
            "color_temp_physical_max",
            "color_capabilities",
        ]
        results = await self.get_attributes(attributes, from_cache=from_cache)
        capabilities = results.get("color_capabilities")

        if capabilities is None:
            # ZCL Version 4 devices don't support the color_capabilities
            # attribute. In this version XY support is mandatory, but we
            # need to probe to determine if the device supports color
            # temperature.
            capabilities = self.CAPABILITIES_COLOR_XY
            result = await self.get_attribute_value(
                "color_temperature", from_cache=from_cache
            )

            if result is not None and result is not self.UNSUPPORTED_ATTRIBUTE:
                capabilities |= self.CAPABILITIES_COLOR_TEMP
        self._color_capabilities = capabilities
        await super().async_initialize(from_cache)
