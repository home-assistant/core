"""
Support for XS1 switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/xs1/
"""
import asyncio
import logging

from homeassistant.helpers.entity import ToggleEntity

from ..xs1 import ACTUATORS, DOMAIN, XS1DeviceEntity

DEPENDENCIES = ['xs1']
_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the XS1 platform."""
    _LOGGER.info("initializing XS1 Switch")

    from xs1_api_client.api_constants import ActuatorType

    actuators = hass.data[DOMAIN][ACTUATORS]

    for actuator in actuators:
        if (actuator.type() == ActuatorType.SWITCH) or \
                (actuator.type() == ActuatorType.DIMMER):
            async_add_devices([XS1SwitchEntity(actuator, hass)])

    _LOGGER.info("Added Switches!")


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

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the device on."""
        self.device.turn_on()
        self.schedule_update_ha_state()

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the device off."""
        self.device.turn_off()
        self.schedule_update_ha_state()
