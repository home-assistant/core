"""
Home automation channels module for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import logging

from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import AttributeListeningChannel
from ..const import CHANNEL_ELECTRICAL_MEASUREMENT, SIGNAL_ATTR_UPDATED

_LOGGER = logging.getLogger(__name__)


class ElectricalMeasurementChannel(AttributeListeningChannel):
    """Channel that polls active power level."""

    CHANNEL_NAME = CHANNEL_ELECTRICAL_MEASUREMENT

    async def async_update(self):
        """Retrieve latest state."""
        self.debug("async_update")

        # This is a polling channel. Don't allow cache.
        result = await self.get_attribute_value("active_power", from_cache=False)
        async_dispatcher_send(
            self._zha_device.hass,
            "{}_{}".format(self.unique_id, SIGNAL_ATTR_UPDATED),
            result,
        )

    async def async_initialize(self, from_cache):
        """Initialize channel."""
        await self.get_attribute_value("active_power", from_cache=from_cache)
        await super().async_initialize(from_cache)
