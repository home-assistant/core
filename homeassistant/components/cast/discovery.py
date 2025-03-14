"""Deal with Cast discovery."""

import logging
import threading

import pychromecast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import (
    CAST_BROWSER_KEY,
    CONF_KNOWN_HOSTS,
    INTERNAL_DISCOVERY_RUNNING_KEY,
    SIGNAL_CAST_DISCOVERED,
    SIGNAL_CAST_REMOVED,
)
from .helpers import ChromecastInfo, ChromeCastZeroconf

_LOGGER = logging.getLogger(__name__)


def discover_chromecast(
    hass: HomeAssistant, cast_info: pychromecast.models.CastInfo
) -> None:
    """Discover a Chromecast."""

    info = ChromecastInfo(
        cast_info=cast_info,
    )

    if info.uuid is None:
        _LOGGER.error("Discovered chromecast without uuid %s", info)
        return

    info = info.fill_out_missing_chromecast_info(hass)
    _LOGGER.debug("Discovered new or updated chromecast %s", info)

    dispatcher_send(hass, SIGNAL_CAST_DISCOVERED, info)


def _remove_chromecast(hass: HomeAssistant, info: ChromecastInfo) -> None:
    # Removed chromecast
    _LOGGER.debug("Removed chromecast %s", info)

    dispatcher_send(hass, SIGNAL_CAST_REMOVED, info)


def setup_internal_discovery(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Set up the pychromecast internal discovery."""
    if INTERNAL_DISCOVERY_RUNNING_KEY not in hass.data:
        hass.data[INTERNAL_DISCOVERY_RUNNING_KEY] = threading.Lock()

    if not hass.data[INTERNAL_DISCOVERY_RUNNING_KEY].acquire(blocking=False):
        # Internal discovery is already running
        return

    class CastListener(pychromecast.discovery.AbstractCastListener):
        """Listener for discovering chromecasts."""

        def add_cast(self, uuid, _):
            """Handle zeroconf discovery of a new chromecast."""
            discover_chromecast(hass, browser.devices[uuid])

        def update_cast(self, uuid, _):
            """Handle zeroconf discovery of an updated chromecast."""
            discover_chromecast(hass, browser.devices[uuid])

        def remove_cast(self, uuid, service, cast_info):
            """Handle zeroconf discovery of a removed chromecast."""
            _remove_chromecast(
                hass,
                ChromecastInfo(
                    cast_info=cast_info,
                ),
            )

    _LOGGER.debug("Starting internal pychromecast discovery")
    browser = pychromecast.discovery.CastBrowser(
        CastListener(),
        ChromeCastZeroconf.get_zeroconf(),
        config_entry.data.get(CONF_KNOWN_HOSTS),
    )
    hass.data[CAST_BROWSER_KEY] = browser
    browser.start_discovery()

    def stop_discovery(event):
        """Stop discovery of new chromecasts."""
        _LOGGER.debug("Stopping internal pychromecast discovery")
        browser.stop_discovery()
        hass.data[INTERNAL_DISCOVERY_RUNNING_KEY].release()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_discovery)

    config_entry.add_update_listener(config_entry_updated)


async def config_entry_updated(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle config entry being updated."""
    browser = hass.data[CAST_BROWSER_KEY]
    browser.host_browser.update_hosts(config_entry.data.get(CONF_KNOWN_HOSTS))
