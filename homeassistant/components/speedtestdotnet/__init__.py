"""Support for testing internet speed via Speedtest.net."""
from datetime import timedelta
import logging

import speedtest

from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
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
    if not await coordinator.async_setup():
        return False

    await coordinator.async_refresh()
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
        self.server_list = {}

    async def async_update_server_list(self):
        """Get list of speedtest servers."""
        self.server_list[DEFAULT_SERVER] = ""
        server_list = await self.hass.async_add_executor_job(self.api.get_servers)
        for server in sorted(
            server_list.values(), key=lambda server: server[0]["country"]
        ):
            self.server_list.update(
                {f"{server[0]['country']} - {server[0]['name']}": server}
            )

    def update_data(self):
        """Get the latest data from speedtest.net."""

        server_id = self.get_server_id()

        self.api.get_servers(servers=[server_id])
        _LOGGER.debug(
            "Executing speedtest.net speed test with server_id: %s", server_id
        )

        self.api.download()
        self.api.upload()

    async def _async_update_data(self, *_):
        """Update Speedtest data."""
        try:
            await self.async_update_server_list()
            await self.hass.async_add_executor_job(self.update_data)
        except speedtest.ConfigRetrievalError:
            raise UpdateFailed
        return self.api.results.dict()

    async def async_setup(self):
        """Set up SpeedTest."""
        try:
            self.api = await self.hass.async_add_executor_job(speedtest.Speedtest)
        except speedtest.ConfigRetrievalError:
            raise ConfigEntryNotReady

        super().__init__(
            self.hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(
                minutes=self.config_entry.options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                )
            ),
        )

        self.hass.services.async_register(
            DOMAIN, SPEED_TEST_SERVICE, self._async_update_data
        )

        return True

    def get_server_id(self):
        """Get server id."""
        server_id = self.config_entry.options.get(CONF_SERVER_ID)
        if not server_id:
            best_server = self.api.get_best_server()
            server_id = best_server.get("id")
            _LOGGER.debug("Best server id detected: %s", server_id)

        return server_id
