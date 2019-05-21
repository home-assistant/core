"""
HVAC channels module for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""
import logging
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from . import ZigbeeChannel
from ..const import SIGNAL_ATTR_UPDATED, SIGNAL_SET_FAN

_LOGGER = logging.getLogger(__name__)


class ThermostatChannel(ZigbeeChannel):
    """Thermostat channel."""

    async def async_set_hold_mode(self, value) -> None:
        """Set the system mode."""
        from zigpy.exceptions import DeliveryError
        try:
            await self.cluster.write_attributes({'temp_setpoint_hold': value})
        except DeliveryError as ex:
            _LOGGER.error("%s: Could not set hold mode: %s", self.unique_id, ex)
            return

    async def async_set_cooling_setpoint(self, value) -> None:
        """Set the cooling setpoint."""
        from zigpy.exceptions import DeliveryError
        try:
            await self.cluster.write_attributes({'occupied_cooling_setpoint': value})
        except DeliveryError as ex:
            _LOGGER.error("%s: Could not set cooling setpoint: %s", self.unique_id, ex)
            return

    async def async_set_heating_setpoint(self, value) -> None:
        """Set the heating setpoint."""
        from zigpy.exceptions import DeliveryError
        try:
            await self.cluster.write_attributes({'occupied_heating_setpoint': value})
        except DeliveryError as ex:
            _LOGGER.error("%s: Could not set heating setpoint: %s", self.unique_id, ex)
            return

    async def async_set_system_mode(self, value) -> None:
        """Set the system mode."""
        from zigpy.exceptions import DeliveryError
        try:
            await self.cluster.write_attributes({'system_mode': value})
        except DeliveryError as ex:
            _LOGGER.error("%s: Could not set system mode: %s", self.unique_id, ex)
            return


    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute update from thermostat cluster."""
        attr_name = self.cluster.attributes.get(attrid, [attrid])[0]
        _LOGGER.debug("%s: Attribute report '%s'[%s] = %s",
                      self.unique_id, self.cluster.name, attr_name, value)
        self.dispatch_send(attr_name, value)

    def dispatch_send(self, name, value):
            async_dispatcher_send(
                self._zha_device.hass,
                "{}_{}".format(self.unique_id, SIGNAL_ATTR_UPDATED),
                name, value
            )

    async def async_configure(self):
        """Configure this channel."""
        await super().async_configure()
        await self.async_initialize(False)

    async def async_initialize(self, from_cache):
        """Initialize channel."""
        await self.get_attribute_value(
            'local_temperature', from_cache=from_cache)
        await self.get_attribute_value(
            'occupied_cooling_setpoint', from_cache=from_cache)
        await self.get_attribute_value(
            'occupied_heating_setpoint', from_cache=from_cache)
        await self.get_attribute_value(
            'min_heat_setpoint_limit', from_cache=from_cache)
        await self.get_attribute_value(
            'max_heat_setpoint_limit', from_cache=from_cache)
        await self.get_attribute_value(
            'min_cool_setpoint_limit', from_cache=from_cache)
        await self.get_attribute_value(
            'max_cool_setpoint_limit', from_cache=from_cache)
        await self.get_attribute_value(
            'ctrl_seqe_of_oper', from_cache=from_cache)
        await self.get_attribute_value(
            'system_mode', from_cache=from_cache)
        await self.get_attribute_value(
            'running_state', from_cache=from_cache)
        await self.get_attribute_value(
            'temp_setpoint_hold', from_cache=from_cache)
        await super().async_initialize(from_cache)


class FanChannel(ZigbeeChannel):
    """Fan channel."""

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
            "{}_{}".format(self.unique_id, SIGNAL_SET_FAN),
            result
        )

    @callback
    def attribute_updated(self, attrid, value):
        """Handle attribute update from fan cluster."""
        attr_name = self.cluster.attributes.get(attrid, [attrid])[0]
        _LOGGER.debug("%s: Attribute report '%s'[%s] = %s",
                      self.unique_id, self.cluster.name, attr_name, value)
        if attr_name == 'fan_mode':
            async_dispatcher_send(
                self._zha_device.hass,
                "{}_{}".format(self.unique_id, SIGNAL_SET_FAN),
                value
            )

    async def async_configure(self):
        """Configure this channel."""
        await super().async_configure()
        await self.async_initialize(False)

    async def async_initialize(self, from_cache):
        """Initialize channel."""
        await self.get_attribute_value(
            'fan_mode', from_cache=from_cache)
        await self.get_attribute_value(
            'fan_mode_sequence', from_cache=from_cache)
        await super().async_initialize(from_cache)
