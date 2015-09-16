"""
homeassistant.components.discovery
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Starts a service to scan in intervals for new devices.

Will emit EVENT_PLATFORM_DISCOVERED whenever a new service has been discovered.

Knows which components handle certain types, will make sure they are
loaded before the EVENT_PLATFORM_DISCOVERED is fired.
"""
import logging
import threading

from homeassistant import bootstrap
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_PLATFORM_DISCOVERED,
    ATTR_SERVICE, ATTR_DISCOVERED)

DOMAIN = "discovery"
DEPENDENCIES = []
REQUIREMENTS = ['netdisco==0.3']

SCAN_INTERVAL = 300  # seconds

# Next 3 lines for now a mirror from netdisco.const
# Should setup a mapping netdisco.const -> own constants
SERVICE_WEMO = 'belkin_wemo'
SERVICE_HUE = 'philips_hue'
SERVICE_CAST = 'google_cast'
SERVICE_NETGEAR = 'netgear_router'

SERVICE_HANDLERS = {
    SERVICE_WEMO: "switch",
    SERVICE_CAST: "media_player",
    SERVICE_HUE: "light",
    SERVICE_NETGEAR: 'device_tracker',
}


def listen(hass, service, callback):
    """
    Setup listener for discovery of specific service.
    Service can be a string or a list/tuple.
    """

    if isinstance(service, str):
        service = (service,)
    else:
        service = tuple(service)

    def discovery_event_listener(event):
        """ Listens for discovery events. """
        if event.data[ATTR_SERVICE] in service:
            callback(event.data[ATTR_SERVICE], event.data[ATTR_DISCOVERED])

    hass.bus.listen(EVENT_PLATFORM_DISCOVERED, discovery_event_listener)


def setup(hass, config):
    """ Starts a discovery service. """
    logger = logging.getLogger(__name__)

    from netdisco.service import DiscoveryService

    # Disable zeroconf logging, it spams
    logging.getLogger('zeroconf').setLevel(logging.CRITICAL)

    lock = threading.Lock()

    def new_service_listener(service, info):
        """ Called when a new service is found. """
        with lock:
            logger.info("Found new service: %s %s", service, info)

            component = SERVICE_HANDLERS.get(service)

            # We do not know how to handle this service
            if not component:
                return

            # Hack - fix when device_tracker supports discovery
            if service == SERVICE_NETGEAR:
                bootstrap.setup_component(hass, component, {
                    'device_tracker': {'platform': 'netgear'}
                })
                return

            # This component cannot be setup.
            if not bootstrap.setup_component(hass, component, config):
                return

            hass.bus.fire(EVENT_PLATFORM_DISCOVERED, {
                ATTR_SERVICE: service,
                ATTR_DISCOVERED: info
            })

    def start_discovery(event):
        """ Start discovering. """
        netdisco = DiscoveryService(SCAN_INTERVAL)
        netdisco.add_listener(new_service_listener)
        netdisco.start()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_discovery)

    return True
