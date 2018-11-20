"""
Support for INSTEON dimmers via PowerLinc Modem.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor.insteon/
"""
import logging

from homeassistant.components.insteon import InsteonEntity
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['insteon']

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the INSTEON device class for the hass platform."""
    insteon_modem = hass.data['insteon'].get('modem')

    address = discovery_info['address']
    device = insteon_modem.devices[address]
    state_key = discovery_info['state_key']

    _LOGGER.debug('Adding device %s entity %s to Sensor platform',
                  device.address.hex, device.states[state_key].name)

    new_entity = InsteonSensorDevice(device, state_key)

    async_add_entities([new_entity])


class InsteonSensorDevice(InsteonEntity, Entity):
    """A Class for an Insteon device."""
