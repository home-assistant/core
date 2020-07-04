"""Deal with Cast discovery."""
import logging
import threading

import pychromecast

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import (
    INTERNAL_DISCOVERY_RUNNING_KEY,
    KNOWN_CHROMECAST_INFO_KEY,
    SIGNAL_CAST_DISCOVERED,
    SIGNAL_CAST_REMOVED,
)
from .helpers import ChromecastInfo, ChromeCastZeroconf

_LOGGER = logging.getLogger(__name__)


def discover_chromecast(hass: HomeAssistant, info: ChromecastInfo):
    """Discover a Chromecast."""
    if info.uuid is None:
        _LOGGER.error("Discovered chromecast without uuid %s", info)
        return

    if info.uuid in hass.data[KNOWN_CHROMECAST_INFO_KEY]:
        _LOGGER.debug("Discovered update for known chromecast %s", info)
    else:
        _LOGGER.debug("Discovered chromecast %s", info)

    hass.data[KNOWN_CHROMECAST_INFO_KEY][info.uuid] = info
    dispatcher_send(hass, SIGNAL_CAST_DISCOVERED, info)


def _remove_chromecast(hass: HomeAssistant, info: ChromecastInfo):
    # Removed chromecast
    _LOGGER.debug("Removed chromecast %s", info)

    dispatcher_send(hass, SIGNAL_CAST_REMOVED, info)


def setup_internal_discovery(hass: HomeAssistant) -> None:
    """Set up the pychromecast internal discovery."""
    if INTERNAL_DISCOVERY_RUNNING_KEY not in hass.data:
        hass.data[INTERNAL_DISCOVERY_RUNNING_KEY] = threading.Lock()

    if not hass.data[INTERNAL_DISCOVERY_RUNNING_KEY].acquire(blocking=False):
        # Internal discovery is already running
        return

    def internal_add_update_callback(uuid, service_name):
        """Handle zeroconf discovery of a new or updated chromecast."""
        service = listener.services[uuid]

        # For support of deprecated IP based white listing
        zconf = ChromeCastZeroconf.get_zeroconf()
        service_info = None
        tries = 0
        while service_info is None and tries < 4:
            try:
                service_info = zconf.get_service_info(
                    "_googlecast._tcp.local.", service_name
                )
            except OSError:
                # If the zeroconf fails to receive the necessary data we abort
                # adding the service
                break
            tries += 1

        if not service_info:
            _LOGGER.warning(
                "setup_internal_discovery failed to get info for %s, %s",
                uuid,
                service_name,
            )
            return

        addresses = service_info.parsed_addresses()
        host = addresses[0] if addresses else service_info.server

        discover_chromecast(
            hass,
            ChromecastInfo(
                services=service[0],
                uuid=service[1],
                model_name=service[2],
                friendly_name=service[3],
                host=host,
                port=service_info.port,
            ),
        )

    def internal_remove_callback(uuid, service_name, service):
        """Handle zeroconf discovery of a removed chromecast."""
        _remove_chromecast(
            hass,
            ChromecastInfo(
                services=service[0],
                uuid=service[1],
                model_name=service[2],
                friendly_name=service[3],
            ),
        )

    _LOGGER.debug("Starting internal pychromecast discovery.")
    listener = pychromecast.CastListener(
        internal_add_update_callback,
        internal_remove_callback,
        internal_add_update_callback,
    )
    browser = pychromecast.start_discovery(listener, ChromeCastZeroconf.get_zeroconf())

    def stop_discovery(event):
        """Stop discovery of new chromecasts."""
        _LOGGER.debug("Stopping internal pychromecast discovery.")
        pychromecast.discovery.stop_discovery(browser)
        hass.data[INTERNAL_DISCOVERY_RUNNING_KEY].release()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_discovery)
