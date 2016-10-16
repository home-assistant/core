"""
Starts a service to scan in intervals for new devices.

Will emit EVENT_PLATFORM_DISCOVERED whenever a new service has been discovered.

Knows which components handle certain types, will make sure they are
loaded before the EVENT_PLATFORM_DISCOVERED is fired.
"""
import logging
import threading

import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.helpers.discovery import load_platform, discover

REQUIREMENTS = ['netdisco==0.7.1']

DOMAIN = 'discovery'

SCAN_INTERVAL = 300  # seconds
SERVICE_NETGEAR = 'netgear_router'
SERVICE_WEMO = 'belkin_wemo'

SERVICE_HANDLERS = {
    SERVICE_NETGEAR: ('device_tracker', None),
    SERVICE_WEMO: ('wemo', None),
    'philips_hue': ('light', 'hue'),
    'google_cast': ('media_player', 'cast'),
    'panasonic_viera': ('media_player', 'panasonic_viera'),
    'plex_mediaserver': ('media_player', 'plex'),
    'roku': ('media_player', 'roku'),
    'sonos': ('media_player', 'sonos'),
    'logitech_mediaserver': ('media_player', 'squeezebox'),
    'directv': ('media_player', 'directv'),
}

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({}),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Start a discovery service."""
    logger = logging.getLogger(__name__)

    from netdisco.service import DiscoveryService

    # Disable zeroconf logging, it spams
    logging.getLogger('zeroconf').setLevel(logging.CRITICAL)

    lock = threading.Lock()

    def new_service_listener(service, info):
        """Called when a new service is found."""
        with lock:
            logger.info("Found new service: %s %s", service, info)

            comp_plat = SERVICE_HANDLERS.get(service)

            # We do not know how to handle this service.
            if not comp_plat:
                return

            component, platform = comp_plat

            if platform is None:
                discover(hass, service, info, component, config)
            else:
                load_platform(hass, component, platform, info, config)

    # pylint: disable=unused-argument
    def start_discovery(event):
        """Start discovering."""
        netdisco = DiscoveryService(SCAN_INTERVAL)
        netdisco.add_listener(new_service_listener)
        netdisco.start()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_discovery)

    return True
