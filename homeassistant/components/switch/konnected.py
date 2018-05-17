"""
Support for wired switches attached to a Konnected device.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.konnected/
"""

import logging

from homeassistant.components.konnected import (
    DOMAIN as KONNECTED_DOMAIN, PIN_TO_ZONE, CONF_ACTIVATION,
    STATE_LOW, STATE_HIGH)
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.const import (CONF_DEVICES, CONF_SWITCHES, ATTR_STATE)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['konnected']


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set switches attached to a Konnected device."""
    if discovery_info is None:
        return

    data = hass.data[KONNECTED_DOMAIN]
    device_id = discovery_info['device_id']
    client = data[CONF_DEVICES][device_id]['client']
    switches = [KonnectedSwitch(device_id, pin_num, pin_data, client)
                for pin_num, pin_data in
                data[CONF_DEVICES][device_id][CONF_SWITCHES].items()]
    async_add_devices(switches)


class KonnectedSwitch(ToggleEntity):
    """Representation of a Konnected switch."""

    def __init__(self, device_id, pin_num, data, client):
        """Initialize the switch."""
        self._data = data
        self._device_id = device_id
        self._pin_num = pin_num
        self._activation = self._data.get(CONF_ACTIVATION, STATE_HIGH)
        self._state = self._boolean_state(self._data.get(ATTR_STATE))
        self._name = self._data.get(
            'name', 'Konnected {} Actuator {}'.format(
                device_id, PIN_TO_ZONE[pin_num]))
        self._client = client
        _LOGGER.debug('Created new switch: %s', self._name)

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self._state

    def turn_on(self, **kwargs):
        """Send a command to turn on the switch."""
        resp = self._client.put_device(
            self._pin_num, int(self._activation == STATE_HIGH))

        if resp.get(ATTR_STATE) is not None:
            self._set_state(self._boolean_state(resp.get(ATTR_STATE)))

    def turn_off(self, **kwargs):
        """Send a command to turn off the switch."""
        resp = self._client.put_device(
            self._pin_num, int(self._activation == STATE_LOW))

        if resp.get(ATTR_STATE) is not None:
            self._set_state(self._boolean_state(resp.get(ATTR_STATE)))

    def _boolean_state(self, int_state):
        if int_state is None:
            return False
        if int_state == 0:
            return self._activation == STATE_LOW
        if int_state == 1:
            return self._activation == STATE_HIGH

    def _set_state(self, state):
        self._state = state
        self.schedule_update_ha_state()
        _LOGGER.debug('Setting status of %s actuator pin %s to %s',
                      self._device_id, self.name, state)

    async def async_added_to_hass(self):
        """Store entity_id."""
        self._data['entity_id'] = self.entity_id
