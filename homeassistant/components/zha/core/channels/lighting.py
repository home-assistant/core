"""
Lighting channels module for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import logging
from . import ZigbeeChannel
from ..const import COLOR_CHANNEL

_LOGGER = logging.getLogger(__name__)


class ColorChannel(ZigbeeChannel):
    """Color channel."""

    CAPABILITIES_COLOR_XY = 0x08
    CAPABILITIES_COLOR_TEMP = 0x10
    UNSUPPORTED_ATTRIBUTE = 0x86

    def __init__(self, cluster, device):
        """Initialize ColorChannel."""
        super().__init__(cluster, device)
        self.name = COLOR_CHANNEL
        self._color_capabilities = None

    def get_color_capabilities(self):
        """Return the color capabilities."""
        return self._color_capabilities

    async def async_initialize(self, from_cache):
        """Initialize channel."""
        capabilities = await self.get_attribute_value(
            'color_capabilities', from_cache=from_cache)

        if capabilities is None:
            # ZCL Version 4 devices don't support the color_capabilities
            # attribute. In this version XY support is mandatory, but we
            # need to probe to determine if the device supports color
            # temperature.
            capabilities = self.CAPABILITIES_COLOR_XY
            result = await self.get_attribute_value(
                'color_temperature', from_cache=from_cache)

            if result is not self.UNSUPPORTED_ATTRIBUTE:
                capabilities |= self.CAPABILITIES_COLOR_TEMP
        self._color_capabilities = capabilities
        await super().async_initialize(from_cache)
