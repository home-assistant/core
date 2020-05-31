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
    if info in hass.data[KNOWN_CHROMECAST_INFO_KEY]:
        _LOGGER.debug("Discovered previous chromecast %s", info)

    # Either discovered completely new chromecast or a "moved" one.
    _LOGGER.debug("Discovered chromecast %s", info)

    if info.uuid is not None:
        # Remove previous cast infos with same uuid from known chromecasts.
        same_uuid = {
            x for x in hass.data[KNOWN_CHROMECAST_INFO_KEY] if info.uuid == x.uuid
        }
        hass.data[KNOWN_CHROMECAST_INFO_KEY] -= same_uuid

    hass.data[KNOWN_CHROMECAST_INFO_KEY].add(info)
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

    def internal_add_callback(name):
        """Handle zeroconf discovery of a new chromecast."""
        mdns = listener.services[name]
        discover_chromecast(
            hass,
            ChromecastInfo(
                service=name,
                host=mdns[0],
                port=mdns[1],
                uuid=mdns[2],
                model_name=mdns[3],
                friendly_name=mdns[4],
            ),
        )

    def internal_remove_callback(name, mdns):
        """Handle zeroconf discovery of a removed chromecast."""
        _remove_chromecast(
            hass,
            ChromecastInfo(
                service=name,
                host=mdns[0],
                port=mdns[1],
                uuid=mdns[2],
                model_name=mdns[3],
                friendly_name=mdns[4],
            ),
        )

    _LOGGER.debug("Starting internal pychromecast discovery.")
    listener, browser = pychromecast.start_discovery(
        internal_add_callback,
        internal_remove_callback,
        ChromeCastZeroconf.get_zeroconf(),
    )

    def stop_discovery(event):
        """Stop discovery of new chromecasts."""
        _LOGGER.debug("Stopping internal pychromecast discovery.")
        pychromecast.stop_discovery(browser)
        hass.data[INTERNAL_DISCOVERY_RUNNING_KEY].release()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_discovery)
