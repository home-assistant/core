"""Support for testing internet speed via Speedtest.net."""
from __future__ import annotations

from datetime import timedelta
import logging

import speedtest

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_MANUAL,
    CONF_SERVER_ID,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SERVER,
    DOMAIN,
    PLATFORMS,
    SPEED_TEST_SERVICE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Speedtest.net component."""
    coordinator = SpeedTestDataCoordinator(hass, config_entry)
    await coordinator.async_setup()

    async def _enable_scheduled_speedtests(*_):
        """Activate the data update coordinator."""
        coordinator.update_interval = timedelta(
            minutes=config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        await coordinator.async_refresh()

    if not config_entry.options.get(CONF_MANUAL, False):
        if hass.state == CoreState.running:
            await _enable_scheduled_speedtests()
        else:
            # Running a speed test during startup can prevent
            # integrations from being able to setup because it
            # can saturate the network interface.
            hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, _enable_scheduled_speedtests
            )

    hass.data[DOMAIN] = coordinator

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload SpeedTest Entry from config_entry."""
    hass.services.async_remove(DOMAIN, SPEED_TEST_SERVICE)

    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        hass.data.pop(DOMAIN)
    return unload_ok


class SpeedTestDataCoordinator(DataUpdateCoordinator):
    """Get the latest data from speedtest.net."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the data object."""
        self.hass = hass
        self.config_entry: ConfigEntry = config_entry
        self.api: speedtest.Speedtest | None = None
        self.servers: dict[str, dict] = {DEFAULT_SERVER: {}}
        super().__init__(
            self.hass,
            _LOGGER,
            name=DOMAIN,
            update_method=self.async_update,
        )

    def initialize(self) -> None:
        """Initialize speedtest api."""
        self.api = speedtest.Speedtest()
        self.update_servers()

    def update_servers(self):
        """Update list of test servers."""
        test_servers = self.api.get_servers()
        test_servers_list = []
        for servers in test_servers.values():
            for server in servers:
                test_servers_list.append(server)
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

    def update_data(self):
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
        return self.api.results.dict()

    async def async_update(self) -> dict[str, str]:
        """Update Speedtest data."""
        try:
            return await self.hass.async_add_executor_job(self.update_data)
        except speedtest.NoMatchedServers as err:
            raise UpdateFailed("Selected server is not found.") from err
        except speedtest.SpeedtestException as err:
            raise UpdateFailed(err) from err

    async def async_setup(self) -> None:
        """Set up SpeedTest."""
        try:
            await self.hass.async_add_executor_job(self.initialize)
        except speedtest.SpeedtestException as err:
            raise ConfigEntryNotReady from err

        async def request_update(call: ServiceCall) -> None:
            """Request update."""
            await self.async_request_refresh()

        self.hass.services.async_register(DOMAIN, SPEED_TEST_SERVICE, request_update)

        self.config_entry.async_on_unload(
            self.config_entry.add_update_listener(options_updated_listener)
        )


async def options_updated_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    if entry.options[CONF_MANUAL]:
        hass.data[DOMAIN].update_interval = None
        return

    hass.data[DOMAIN].update_interval = timedelta(
        minutes=entry.options[CONF_SCAN_INTERVAL]
    )
    await hass.data[DOMAIN].async_request_refresh()
