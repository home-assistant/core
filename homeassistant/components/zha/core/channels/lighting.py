"""Lighting channels module for Zigbee Home Automation."""
import asyncio
import logging
from typing import Dict, List, Tuple, Union

import zigpy.exceptions
import zigpy.zcl.clusters.lighting as lighting
import zigpy.zcl.foundation as zcl_f

from .. import registries, typing as zha_typing
from ..const import REPORT_CONFIG_DEFAULT
from .base import ClientChannel, ZigbeeChannel

_LOGGER = logging.getLogger(__name__)


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
    def min_mireds(self):
        """Return the coldest color_temp that this channel supports."""
        return self._min_mireds

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this channel supports."""
        return self._max_mireds

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

    async def configure_reporting(self):
        """Configure attribute reporting for a cluster.

        This also swallows DeliveryError exceptions that are thrown when
        devices are unreachable.
        """
        kwargs = {}
        if self.cluster.cluster_id >= 0xFC00 and self._ch_pool.manufacturer_code:
            kwargs["manufacturer"] = self._ch_pool.manufacturer_code

        chunk, rest = self._report_config[:4], self._report_config[4:]
        while chunk:
            attrs = {record["attr"]: record["config"] for record in chunk}
            try:
                res = await self.cluster.configure_reporting_multiple(attrs, **kwargs)
                self._configure_reporting_status(attrs, res)
            except (zigpy.exceptions.DeliveryError, asyncio.TimeoutError) as ex:
                self.debug(
                    "failed to set reporting on '%s' cluster for: %s",
                    self.cluster.ep_attribute,
                    str(ex),
                )
                break
            chunk, rest = rest[:4], rest[4:]

    def _configure_reporting_status(
        self, attrs: Dict[Union[int, str], Tuple], res: Union[List, Tuple]
    ) -> None:
        """Parse configure reporting result."""
        res = res[0]
        if not isinstance(res, list):
            # assume default response
            self.debug(
                "attr reporting for '%s' on '%s': %s", attrs, self.name, res,
            )
            return
        if res[0].status == zcl_f.Status.SUCCESS:
            self.debug(
                "Successfully configured reporting for '%s' on '%s' cluster: %s",
                attrs,
                self.name,
                res,
            )
            return

        failed = {self.cluster.attributes.get(r.attrid, [r.attrid])[0] for r in res}
        attrs = {self.cluster.attributes.get(r, [r])[0] for r in attrs}
        self.debug(
            "Successfully configured reporting for '%s' on '%s' cluster",
            attrs - failed,
            self.name,
        )
        self.debug(
            "Failed to configure reporting for '%s' on '%s' cluster: %s",
            failed,
            self.name,
            res,
        )

    async def fetch_color_capabilities(self, from_cache):
        """Get the color configuration."""
        attributes = [
            "color_temp_physical_min",
            "color_temp_physical_max",
            "color_capabilities",
        ]
        results = await self.get_attributes(attributes, from_cache=from_cache)
        capabilities = results.get("color_capabilities")
        self._min_mireds = results.get("color_temp_physical_min", 153)
        self._max_mireds = results.get("color_temp_physical_max", 500)

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
