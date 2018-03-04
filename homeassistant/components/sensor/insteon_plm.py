"""
Support for INSTEON dimmers via PowerLinc Modem.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor.insteon_plm/
"""
import asyncio
import logging

from homeassistant.components.insteon_plm import InsteonPLMEntity
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['insteon_plm']

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the INSTEON PLM device class for the hass platform."""
    plm = hass.data['insteon_plm']

    address = discovery_info['address']
    device = plm.devices[address]
    state_key = discovery_info['state_key']

    _LOGGER.debug('Adding device %s entity %s to Sensor platform',
                  device.address.hex, device.states[state_key].name)

    new_entity = InsteonPLMSensorDevice(device, state_key)

    async_add_devices([new_entity])


class InsteonPLMSensorDevice(InsteonPLMEntity, Entity):
    """A Class for an Insteon device."""
