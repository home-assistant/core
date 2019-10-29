"""Support for testing internet speed via Speedtest.net."""
from datetime import timedelta
import logging

import speedtest
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_SCAN_INTERVAL
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_MANUAL,
    CONF_SERVER_ID,
    DATA_UPDATED,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SPEED_TEST_SERVICE,
)

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_SERVER_ID): cv.positive_int,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(cv.time_period, cv.positive_timedelta),
                vol.Optional(CONF_MANUAL, default=False): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Import the Speedtest.net component from config."""
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up the Speedtest.net component."""

    client = SpeedTestClient(hass, config_entry)
    hass.data[DOMAIN] = client

    if not await client.async_setup():
        return False

    return True


async def async_unload_entry(hass, config_entry):
    """Unload SpeedTest Entry from config_entry."""
    hass.services.async_remove(DOMAIN, SPEED_TEST_SERVICE)
    if hass.data[DOMAIN].unsub_timer:
        hass.data[DOMAIN].unsub_timer()

    await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")

    hass.data.pop(DOMAIN)

    return True


class SpeedTestClient:
    """Get the latest data from speedtest.net."""

    def __init__(self, hass, config_entry):
        """Initialize the data object."""
        self.hass = hass
        self.config_entry = config_entry
        self.data = None
        self.api = None
        self.unsub_timer = None

    def update(self):
        """Get the latest data from speedtest.net."""

        _LOGGER.debug("Executing speedtest.net speed test")

        if self.config_entry.options[CONF_SERVER_ID]:
            server_id = [self.config_entry.options[CONF_SERVER_ID]]
            self.api.get_servers(servers=server_id)
            self.api.closest.clear()

        self.api.get_best_server()
        self.api.download()
        self.api.upload()
        self.data = self.api.results.dict()

        async_dispatcher_send(self.hass, DATA_UPDATED)
        _LOGGER.debug("Speed test data updated")

    async def async_setup(self):
        """Set up SpeedTest."""
        self.api = speedtest.Speedtest()
        self.add_options()
        self.set_scan_interval(self.config_entry.options)

        async def update(service=None):
            """Service call to manually update the data."""
            await self.hass.async_add_executor_job(self.update)

        self.hass.services.async_register(DOMAIN, SPEED_TEST_SERVICE, update)

        self.hass.async_create_task(
            self.hass.config_entries.async_forward_entry_setup(
                self.config_entry, "sensor"
            )
        )
        self.config_entry.add_update_listener(self.async_options_updated)

        return True

    def set_scan_interval(self, options):
        """Update scan interval."""

        def refresh(event_time):
            """Get the latest data from SpeedTest."""
            self.update()

        if self.unsub_timer is not None:
            self.unsub_timer()

        if not options[CONF_MANUAL]:
            self.unsub_timer = async_track_time_interval(
                self.hass, refresh, timedelta(minutes=options[CONF_SCAN_INTERVAL])
            )

    def add_options(self):
        """Add options for entry."""
        if not self.config_entry.options:
            scan_interval = self.config_entry.data.pop(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            )
            man_update = self.config_entry.data.pop(CONF_MANUAL, False)
            server_id = self.config_entry.data.pop(CONF_SERVER_ID, None)
            if not server_id:
                best_server = self.api.get_best_server()
                server_id = best_server.get("id")

            options = {
                CONF_SCAN_INTERVAL: scan_interval,
                CONF_MANUAL: man_update,
                CONF_SERVER_ID: server_id,
            }

            self.hass.config_entries.async_update_entry(
                self.config_entry, options=options
            )

    @staticmethod
    async def async_options_updated(hass, entry):
        """Triggered by config entry options updates."""
        hass.data[DOMAIN].set_scan_interval(entry.options)
