"""
Support for Vera switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.vera/
"""
import logging

from homeassistant.components.hdmi_cec import CecDevice, CEC_DEVICES, CEC_CLIENT, DOMAIN
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import STATE_ON, STATE_OFF

DEPENDENCIES = ['hdmi_cec']

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + '.{}'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Find and return Vera switches."""
    _LOGGER.info("setting CEC switches %s", CEC_DEVICES['switch'])
    add_devices(
        CecSwitch(hass, CEC_CLIENT, device) for
        device in CEC_DEVICES['switch'])


class CecSwitch(CecDevice, SwitchDevice):
    """Representation of a Vera Switch."""

    def __init__(self, hass, cec_client, logical):
        """Initialize the Vera device."""
        self._state = False
        CecDevice.__init__(self, hass, cec_client, logical)

    def toggle(self, **kwargs):
        self.turn_off() if self._state else self.turn_on()

    def turn_on(self):
        """Turn device on."""
        self.cec_client.send_command_power_on(self._logical_address)
        self._state = STATE_ON
        self.schedule_update_ha_state()
        self._request_cec_power_status()

    def turn_off(self):
        """Turn device off."""
        self.cec_client.SendCommandStandby(self._logical_address)
        self._state = STATE_OFF
        self.schedule_update_ha_state()
        self._request_cec_power_status()
