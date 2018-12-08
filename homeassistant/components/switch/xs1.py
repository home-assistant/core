"""
Support for XS1 switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/xs1/
"""
import asyncio
import logging
from functools import partial

from homeassistant.helpers.entity import ToggleEntity

from ..xs1 import ACTUATORS, DOMAIN, XS1DeviceEntity

DEPENDENCIES = ['xs1']
_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_devices, discovery_info=None):
    """Setup the XS1 platform."""
    _LOGGER.debug("initializing XS1 Switch")

    from xs1_api_client.api_constants import ActuatorType

    actuators = hass.data[DOMAIN][ACTUATORS]

    switch_entities = []
    for actuator in actuators:
        if (actuator.type() == ActuatorType.SWITCH) or \
                (actuator.type() == ActuatorType.DIMMER):
            switch_entities.append(XS1SwitchEntity(actuator))

    async_add_devices(switch_entities)

    _LOGGER.debug("Added Switches!")


class XS1SwitchEntity(XS1DeviceEntity, ToggleEntity):
    """Representation of a XS1 switch actuator."""

    @property
    def name(self):
        """Return the name of the device if any."""
        return self.device.name()

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.device.value() == 100

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self.hass.async_add_executor_job(
            partial(self.device.turn_on))
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self.hass.async_add_executor_job(
            partial(self.device.turn_off))
        self.async_schedule_update_ha_state()
