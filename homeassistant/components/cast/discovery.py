"""Deal with Cast discovery."""
import logging
import threading

import pychromecast

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import (
    DEFAULT_PORT,
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

    info = info.fill_out_missing_chromecast_info()
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

    class CastListener(pychromecast.discovery.AbstractCastListener):
        def _add_update_cast(self, uuid):
            """Handle zeroconf discovery of a new or updated chromecast."""
            device_info = browser.devices[uuid]

            discover_chromecast(
                hass,
                ChromecastInfo(
                    services=device_info.services,
                    uuid=device_info.uuid,
                    model_name=device_info.model_name,
                    friendly_name=device_info.friendly_name,
                    is_audio_group=device_info.port != DEFAULT_PORT,
                ),
            )

        def add_cast(self, uuid, _):
            """Handle zeroconf discovery of a new chromecast."""
            self._add_update_cast(uuid)

        def update_cast(self, uuid, _):
            """Handle zeroconf discovery of an updated chromecast."""
            self._add_update_cast(uuid)

        def remove_cast(self, uuid, service, device_info):
            """Handle zeroconf discovery of a removed chromecast."""
            _remove_chromecast(
                hass,
                ChromecastInfo(
                    services=device_info.services,
                    uuid=device_info.uuid,
                    model_name=device_info.model_name,
                    friendly_name=device_info.friendly_name,
                ),
            )

    _LOGGER.debug("Starting internal pychromecast discovery")
    browser = pychromecast.discovery.CastBrowser(
        CastListener(), ChromeCastZeroconf.get_zeroconf()
    )
    browser.start_discovery()

    def stop_discovery(event):
        """Stop discovery of new chromecasts."""
        _LOGGER.debug("Stopping internal pychromecast discovery")
        browser.stop_discovery()
        hass.data[INTERNAL_DISCOVERY_RUNNING_KEY].release()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_discovery)
