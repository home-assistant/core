"""Create a switch to trigger an alarm in Noonlight"""
import logging

from homeassistant.components.switch import SwitchDevice

from . import DOMAIN

DEFAULT_NAME = 'noonlight_switch'



_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Create a switch to create an alarm with the Noonlight service"""
    noonlight_platform = hass.data[DOMAIN]
    noonlight_switch = NoonlightSwitch(noonlight_platform)
    async_add_entities([noonlight_switch])


class NoonlightSwitch(SwitchDevice):
    """Representation of a Noonlight alarm switch."""

    def __init__(self, noonlight_platform):
        """Initialize the Noonlight switch."""
        self.noonlight = noonlight_platform
        self._name = DEFAULT_NAME
        self._alarm = None
        self._state = False

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name
        
    @property
    def available(self):
        """ensure that the Noonlight access token is valid"""
        return self.noonlight.access_token_expires_in.total_seconds() > 0

    @property
    def is_on(self):
        """Return the status of the switch."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Activate an alarm"""
        #[TODO] read list of monitored sensors, use sensor type to determine 
        #   whether medical, fire, or police should be notified
        if self._alarm is None:
            self._alarm = await self.noonlight.client.create_alarm(
                body = {
                    'location.coordinates': {
                        'lat':self.noonlight.latitude, 
                        'lng':self.noonlight.latitude, 
                        'accuracy': 5
                    } 
                }
            )
            if self._alarm and self._alarm.status == 'ACTIVE':
                self._state = True        

    async def async_turn_off(self, **kwargs):
        """Send a command to cancel the active alarm"""
        if self._alarm is not None:
            response = await self._alarm.cancel()
            if response:
                self._alarm = None
                self._state = False
