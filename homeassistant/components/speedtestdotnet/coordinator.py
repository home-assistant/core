"""Coordinator for speedtestdotnet."""

from datetime import timedelta
import logging
from typing import Any, cast

import speedtest

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SERVER_ID, DEFAULT_SCAN_INTERVAL, DEFAULT_SERVER, DOMAIN

_LOGGER = logging.getLogger(__name__)

type SpeedTestConfigEntry = ConfigEntry[SpeedTestDataCoordinator]


class SpeedTestDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Get the latest data from speedtest.net."""

    config_entry: SpeedTestConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SpeedTestConfigEntry,
        api: speedtest.Speedtest,
    ) -> None:
        """Initialize the data object."""
        self.hass = hass
        self.api = api
        self.servers: dict[str, dict] = {DEFAULT_SERVER: {}}
        super().__init__(
            self.hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL),
        )

    def update_servers(self) -> None:
        """Update list of test servers."""
        test_servers = self.api.get_servers()
        test_servers_list = [
            server for servers in test_servers.values() for server in servers
        ]
        for server in sorted(
            test_servers_list,
            key=lambda server: (
                server["country"],
                server["name"],
                server["sponsor"],
            ),
        ):
            self.servers[
                f"{server['country']} - {server['sponsor']} - {server['name']}"
            ] = server

    def update_data(self) -> dict[str, Any]:
        """Get the latest data from speedtest.net."""
        self.update_servers()
        self.api.closest.clear()
        if self.config_entry.options.get(CONF_SERVER_ID):
            server_id = self.config_entry.options.get(CONF_SERVER_ID)
            self.api.get_servers(servers=[server_id])

        best_server = self.api.get_best_server()
        _LOGGER.debug(
            "Executing speedtest.net speed test with server_id: %s",
            best_server["id"],
        )
        self.api.download()
        self.api.upload()
        return cast(dict[str, Any], self.api.results.dict())

    async def _async_update_data(self) -> dict[str, Any]:
        """Update Speedtest data."""
        try:
            return await self.hass.async_add_executor_job(self.update_data)
        except speedtest.NoMatchedServers as err:
            raise UpdateFailed("Selected server is not found.") from err
        except speedtest.SpeedtestException as err:
            raise UpdateFailed(err) from err
