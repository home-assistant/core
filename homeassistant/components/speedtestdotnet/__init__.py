"""Support for testing internet speed via Speedtest.net."""
from datetime import timedelta
import logging

import speedtest

from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_MANUAL,
    CONF_SERVER_ID,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SERVER,
    DOMAIN,
    SPEED_TEST_SERVICE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Intergation no longer supports importing from config."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up the Speedtest.net component."""
    coordinator = SpeedTestDataCoordinator(hass, config_entry)
    await coordinator.async_setup()

    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN] = coordinator

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload SpeedTest Entry from config_entry."""
    hass.services.async_remove(DOMAIN, SPEED_TEST_SERVICE)

    await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")

    hass.data.pop(DOMAIN)

    return True


class SpeedTestDataCoordinator(DataUpdateCoordinator):
    """Get the latest data from speedtest.net."""

    def __init__(self, hass, config_entry):
        """Initialize the data object."""
        self.hass = hass
        self.config_entry = config_entry
        self.api = None
        self.servers = {}
        super().__init__(
            self.hass,
            _LOGGER,
            name=DOMAIN,
            update_method=self.async_update,
            update_interval=timedelta(
                seconds=self.config_entry.options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                )
            ),
        )

    def update_data(self):
        """Get the latest data from speedtest.net."""
        server_list = self.api.get_servers()

        self.servers[DEFAULT_SERVER] = None
        for server in sorted(
            server_list.values(), key=lambda server: server[0]["country"]
        ):
            self.servers[f"{server[0]['country']} - {server[0]['name']}"] = server

        if self.config_entry.options.get(CONF_SERVER_ID):
            server_id = self.config_entry.options.get(CONF_SERVER_ID)
            self.api.closest.clear()
            self.api.get_servers(servers=[server_id])
            self.api.get_best_server()
        _LOGGER.debug(
            "Executing speedtest.net speed test with server_id: %s", self.api.best["id"]
        )

        self.api.download()
        self.api.upload()
        return self.api.results.dict()

    async def async_update(self, *_):
        """Update Speedtest data."""
        try:
            return await self.hass.async_add_executor_job(self.update_data)
        except (speedtest.ConfigRetrievalError, speedtest.NoMatchedServers):
            raise UpdateFailed

    async def async_setup(self):
        """Set up SpeedTest."""
        try:
            self.api = await self.hass.async_add_executor_job(speedtest.Speedtest)
        except speedtest.ConfigRetrievalError:
            raise ConfigEntryNotReady

        async def request_update(event):
            """Request update."""
            await self.async_request_refresh()

        self.hass.services.async_register(DOMAIN, SPEED_TEST_SERVICE, request_update)

        self.config_entry.add_update_listener(options_updated_listener)


async def options_updated_listener(hass, entry):
    """Handle options update."""
    if not entry.options[CONF_MANUAL]:
        hass.data[DOMAIN].update_interval = timedelta(
            minutes=entry.options[CONF_SCAN_INTERVAL]
        )
        await hass.data[DOMAIN].async_request_refresh()
        return
    # set the update interval to a very long time
    # if the user wants to disable auto update
    hass.data[DOMAIN].update_interval = timedelta(days=7)
