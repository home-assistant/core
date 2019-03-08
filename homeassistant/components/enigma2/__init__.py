"""Support for Enigma2 devices."""
from homeassistant.components.discovery import SERVICE_ENIGMA2
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers import discovery

DOMAIN = 'enigma2'


def setup(hass, config):
    """Set up the Enigma2 platform."""
    def device_discovered(service, info):
        """Handle when an Enigma2 device has been discovered."""
        load_platform(hass, 'media_player', DOMAIN, info, config)

    discovery.listen(
        hass, SERVICE_ENIGMA2, device_discovered)

    return True
