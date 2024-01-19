"""Lighting cluster handlers module for Zigbee Home Automation."""
from __future__ import annotations

from zigpy.zcl.clusters import lighting

from homeassistant.backports.functools import cached_property

from .. import registries
from ..const import REPORT_CONFIG_DEFAULT
from . import AttrReportConfig, ClientClusterHandler, ClusterHandler


@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(lighting.Ballast.cluster_id)
class Ballast(ClusterHandler):
    """Ballast cluster handler."""


@registries.CLIENT_CLUSTER_HANDLER_REGISTRY.register(lighting.Color.cluster_id)
class ColorClientClusterHandler(ClientClusterHandler):
    """Color client cluster handler."""


@registries.BINDABLE_CLUSTERS.register(lighting.Color.cluster_id)
@registries.ZIGBEE_CLUSTER_HANDLER_REGISTRY.register(lighting.Color.cluster_id)
class ColorClusterHandler(ClusterHandler):
    """Color cluster handler."""

    REPORT_CONFIG = (
        AttrReportConfig(
            attr=lighting.Color.AttributeDefs.current_x.name,
            config=REPORT_CONFIG_DEFAULT,
        ),
        AttrReportConfig(
            attr=lighting.Color.AttributeDefs.current_y.name,
            config=REPORT_CONFIG_DEFAULT,
        ),
        AttrReportConfig(
            attr=lighting.Color.AttributeDefs.current_hue.name,
            config=REPORT_CONFIG_DEFAULT,
        ),
        AttrReportConfig(
            attr=lighting.Color.AttributeDefs.current_saturation.name,
            config=REPORT_CONFIG_DEFAULT,
        ),
        AttrReportConfig(
            attr=lighting.Color.AttributeDefs.color_temperature.name,
            config=REPORT_CONFIG_DEFAULT,
        ),
    )
    MAX_MIREDS: int = 500
    MIN_MIREDS: int = 153
    ZCL_INIT_ATTRS = {
        lighting.Color.AttributeDefs.color_mode.name: False,
        lighting.Color.AttributeDefs.color_temp_physical_min.name: True,
        lighting.Color.AttributeDefs.color_temp_physical_max.name: True,
        lighting.Color.AttributeDefs.color_capabilities.name: True,
        lighting.Color.AttributeDefs.color_loop_active.name: False,
        lighting.Color.AttributeDefs.enhanced_current_hue.name: False,
        lighting.Color.AttributeDefs.start_up_color_temperature.name: True,
        lighting.Color.AttributeDefs.options.name: True,
    }

    @cached_property
    def color_capabilities(self) -> lighting.Color.ColorCapabilities:
        """Return ZCL color capabilities of the light."""
        color_capabilities = self.cluster.get(
            lighting.Color.AttributeDefs.color_capabilities.name
        )
        if color_capabilities is None:
            return lighting.Color.ColorCapabilities.XY_attributes
        return lighting.Color.ColorCapabilities(color_capabilities)

    @property
    def color_mode(self) -> int | None:
        """Return cached value of the color_mode attribute."""
        return self.cluster.get(lighting.Color.AttributeDefs.color_mode.name)

    @property
    def color_loop_active(self) -> int | None:
        """Return cached value of the color_loop_active attribute."""
        return self.cluster.get(lighting.Color.AttributeDefs.color_loop_active.name)

    @property
    def color_temperature(self) -> int | None:
        """Return cached value of color temperature."""
        return self.cluster.get(lighting.Color.AttributeDefs.color_temperature.name)

    @property
    def current_x(self) -> int | None:
        """Return cached value of the current_x attribute."""
        return self.cluster.get(lighting.Color.AttributeDefs.current_x.name)

    @property
    def current_y(self) -> int | None:
        """Return cached value of the current_y attribute."""
        return self.cluster.get(lighting.Color.AttributeDefs.current_y.name)

    @property
    def current_hue(self) -> int | None:
        """Return cached value of the current_hue attribute."""
        return self.cluster.get(lighting.Color.AttributeDefs.current_hue.name)

    @property
    def enhanced_current_hue(self) -> int | None:
        """Return cached value of the enhanced_current_hue attribute."""
        return self.cluster.get(lighting.Color.AttributeDefs.enhanced_current_hue.name)

    @property
    def current_saturation(self) -> int | None:
        """Return cached value of the current_saturation attribute."""
        return self.cluster.get(lighting.Color.AttributeDefs.current_saturation.name)

    @property
    def min_mireds(self) -> int:
        """Return the coldest color_temp that this cluster handler supports."""
        min_mireds = self.cluster.get(
            lighting.Color.AttributeDefs.color_temp_physical_min.name, self.MIN_MIREDS
        )
        if min_mireds == 0:
            self.warning(
                (
                    "[Min mireds is 0, setting to %s] Please open an issue on the"
                    " quirks repo to have this device corrected"
                ),
                self.MIN_MIREDS,
            )
            min_mireds = self.MIN_MIREDS
        return min_mireds

    @property
    def max_mireds(self) -> int:
        """Return the warmest color_temp that this cluster handler supports."""
        max_mireds = self.cluster.get(
            lighting.Color.AttributeDefs.color_temp_physical_max.name, self.MAX_MIREDS
        )
        if max_mireds == 0:
            self.warning(
                (
                    "[Max mireds is 0, setting to %s] Please open an issue on the"
                    " quirks repo to have this device corrected"
                ),
                self.MAX_MIREDS,
            )
            max_mireds = self.MAX_MIREDS
        return max_mireds

    @property
    def hs_supported(self) -> bool:
        """Return True if the cluster handler supports hue and saturation."""
        return (
            self.color_capabilities is not None
            and lighting.Color.ColorCapabilities.Hue_and_saturation
            in self.color_capabilities
        )

    @property
    def enhanced_hue_supported(self) -> bool:
        """Return True if the cluster handler supports enhanced hue and saturation."""
        return (
            self.color_capabilities is not None
            and lighting.Color.ColorCapabilities.Enhanced_hue in self.color_capabilities
        )

    @property
    def xy_supported(self) -> bool:
        """Return True if the cluster handler supports xy."""
        return (
            self.color_capabilities is not None
            and lighting.Color.ColorCapabilities.XY_attributes
            in self.color_capabilities
        )

    @property
    def color_temp_supported(self) -> bool:
        """Return True if the cluster handler supports color temperature."""
        return (
            self.color_capabilities is not None
            and lighting.Color.ColorCapabilities.Color_temperature
            in self.color_capabilities
        ) or self.color_temperature is not None

    @property
    def color_loop_supported(self) -> bool:
        """Return True if the cluster handler supports color loop."""
        return (
            self.color_capabilities is not None
            and lighting.Color.ColorCapabilities.Color_loop in self.color_capabilities
        )

    @property
    def options(self) -> lighting.Color.Options:
        """Return ZCL options of the cluster handler."""
        return lighting.Color.Options(
            self.cluster.get(lighting.Color.AttributeDefs.options.name, 0)
        )

    @property
    def execute_if_off_supported(self) -> bool:
        """Return True if the cluster handler can execute commands when off."""
        return lighting.Color.Options.Execute_if_off in self.options
