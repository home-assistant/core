"""
HVAC channels module for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/integrations/zha/
"""
import logging

from zigpy.exceptions import DeliveryError
import zigpy.zcl.clusters.hvac as hvac

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import ZigbeeChannel
from .. import registries
from ..const import REPORT_CONFIG_OP, SIGNAL_ATTR_UPDATED

_LOGGER = logging.getLogger(__name__)


@registries.ZIGBEE_CHANNEL_REGISTRY.register(hvac.Dehumidification.cluster_id)
class Dehumidification(ZigbeeChannel):
    """Dehumidification channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(hvac.Fan.cluster_id)
class FanChannel(ZigbeeChannel):
    """Fan channel."""

    _value_attribute = 0

    REPORT_CONFIG = ({"attr": "fan_mode", "config": REPORT_CONFIG_OP},)

    async def async_set_speed(self, value) -> None:
        """Set the speed of the fan."""

        try:
            await self.cluster.write_attributes({"fan_mode": value})
        except DeliveryError as ex:
            self.error("Could not set speed: %s", ex)
            return

    async def async_update(self):
        """Retrieve latest state."""
        result = await self.get_attribute_value("fan_mode", from_cache=True)

        async_dispatcher_send(
            self._zha_device.hass, f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}", result
        )

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute update from fan cluster."""
        attr_name = self.cluster.attributes.get(attrid, [attrid])[0]
        self.debug(
            "Attribute report '%s'[%s] = %s", self.cluster.name, attr_name, value
        )
        if attrid == self._value_attribute:
            async_dispatcher_send(
                self._zha_device.hass, f"{self.unique_id}_{SIGNAL_ATTR_UPDATED}", value
            )

    async def async_initialize(self, from_cache):
        """Initialize channel."""
        await self.get_attribute_value(self._value_attribute, from_cache=from_cache)
        await super().async_initialize(from_cache)


@registries.ZIGBEE_CHANNEL_REGISTRY.register(hvac.Pump.cluster_id)
class Pump(ZigbeeChannel):
    """Pump channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(hvac.Thermostat.cluster_id)
class Thermostat(ZigbeeChannel):
    """Thermostat channel."""

    pass


@registries.ZIGBEE_CHANNEL_REGISTRY.register(hvac.UserInterface.cluster_id)
class UserInterface(ZigbeeChannel):
    """User interface (thermostat) channel."""

    pass
