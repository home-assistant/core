"""Support for testing internet speed via Speedtest.net."""
from datetime import timedelta
import logging

import speedtest

from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.exceptions import ConfigEntryNotReady
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


async def async_setup(hass, config):
    """Intergation no longer supports importing from config."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up the Speedtest.net component."""

    client = SpeedTestClient(hass, config_entry)

    if not await client.async_setup():
        return False

    hass.data[DOMAIN] = client

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

    @property
    def scan_interval(self):
        """Return the scan interval duration."""
        if not self.config_entry.options.get(CONF_MANUAL):
            return self.config_entry.options.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            )
        return None

    def update_data(self):
        """Get the latest data from speedtest.net."""

        server_id = self.get_server_id()
        self.api.get_servers(servers=[server_id])

        _LOGGER.debug(
            "Executing speedtest.net speed test with server_id: %s", server_id
        )
        self.api.download()
        self.api.upload()
        self.data = self.api.results.dict()

        async_dispatcher_send(self.hass, DATA_UPDATED)
        _LOGGER.debug("Speed test data updated")

    async def async_update(self, *_):
        """Update Speedtest data."""
        await self.hass.async_add_executor_job(self.update_data)

    async def async_setup(self):
        """Set up SpeedTest."""
        try:
            self.api = await self.hass.async_add_executor_job(speedtest.Speedtest)
        except speedtest.ConfigRetrievalError:
            raise ConfigEntryNotReady
        await self.async_set_scan_interval()

        self.hass.services.async_register(DOMAIN, SPEED_TEST_SERVICE, self.async_update)

        self.hass.async_create_task(
            self.hass.config_entries.async_forward_entry_setup(
                self.config_entry, "sensor"
            )
        )

        self.config_entry.add_update_listener(self.async_options_updated)

        return True

    async def async_set_scan_interval(self):
        """Update scan interval."""

        async def async_refresh(event_time):
            """Get the latest data from SpeedTest."""
            await self.async_update()

        if self.unsub_timer is not None:
            self.unsub_timer()

        if self.scan_interval:
            self.unsub_timer = async_track_time_interval(
                self.hass, async_refresh, timedelta(minutes=self.scan_interval),
            )
            _LOGGER.debug(
                "Speedtest is scheduled to run every %s minutes", self.scan_interval
            )
        self.hass.helpers.event.async_call_later(10, self.async_update)

    def get_server_id(self):
        """Get server id."""
        server_id = self.config_entry.options.get(CONF_SERVER_ID)
        if not server_id:
            best_server = self.api.get_best_server()
            server_id = best_server.get("id")
            _LOGGER.debug("Best server id detected: %s", server_id)

        return server_id

    @staticmethod
    async def async_options_updated(hass, entry):
        """Triggered by config entry options updates."""
        await hass.data[DOMAIN].async_set_scan_interval()
