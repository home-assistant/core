"""
HVAC channels module for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import logging
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from . import ZigbeeChannel
from ..const import SIGNAL_ATTR_UPDATED

_LOGGER = logging.getLogger(__name__)


class FanChannel(ZigbeeChannel):
    """Fan channel."""

    _value_attribute = 0

    async def async_set_speed(self, value) -> None:
        """Set the speed of the fan."""
        from zigpy.exceptions import DeliveryError
        try:
            await self.cluster.write_attributes({'fan_mode': value})
        except DeliveryError as ex:
            _LOGGER.error("%s: Could not set speed: %s", self.unique_id, ex)
            return

    async def async_update(self):
        """Retrieve latest state."""
        result = await self.get_attribute_value('fan_mode', from_cache=True)

        async_dispatcher_send(
            self._zha_device.hass,
            "{}_{}".format(self.unique_id, SIGNAL_ATTR_UPDATED),
            result
        )

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute update from fan cluster."""
        attr_name = self.cluster.attributes.get(attrid, [attrid])[0]
        _LOGGER.debug("%s: Attribute report '%s'[%s] = %s",
                      self.unique_id, self.cluster.name, attr_name, value)
        if attrid == self._value_attribute:
            async_dispatcher_send(
                self._zha_device.hass,
                "{}_{}".format(self.unique_id, SIGNAL_ATTR_UPDATED),
                value
            )

    async def async_initialize(self, from_cache):
        """Initialize channel."""
        await self.get_attribute_value(
            self._value_attribute, from_cache=from_cache)
        await super().async_initialize(from_cache)
