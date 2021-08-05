"""Support for testing internet speed via Speedtest.net."""
from __future__ import annotations

from datetime import timedelta
import logging

import speedtest
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS,
    CONF_SCAN_INTERVAL,
    EVENT_HOMEASSISTANT_STARTED,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_MANUAL,
    CONF_SERVER_ID,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SERVER,
    DOMAIN,
    PLATFORMS,
    SENSOR_TYPES,
    SPEED_TEST_SERVICE,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        # Deprecated in Home Assistant 2021.6
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Optional(CONF_SERVER_ID): cv.positive_int,
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=timedelta(minutes=DEFAULT_SCAN_INTERVAL),
                    ): cv.positive_time_period,
                    vol.Optional(CONF_MANUAL, default=False): cv.boolean,
                    vol.Optional(
                        CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)
                    ): vol.All(cv.ensure_list, [vol.In(list(SENSOR_TYPES))]),
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


def server_id_valid(server_id: str) -> bool:
    """Check if server_id is valid."""
    try:
        api = speedtest.Speedtest()
        api.get_servers([int(server_id)])
    except (speedtest.ConfigRetrievalError, speedtest.NoMatchedServers):
        return False

    return True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Import integration from config."""
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )
    return True


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

    def update_servers(self):
        """Update list of test servers."""
        test_servers = self.api.get_servers()
        test_servers_list = []
        for servers in test_servers.values():
            for server in servers:
                test_servers_list.append(server)
        if test_servers_list:
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

    async def async_set_options(self):
        """Set options for entry."""
        if not self.config_entry.options:
            data = {**self.config_entry.data}
            options = {
                CONF_SCAN_INTERVAL: data.pop(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                CONF_MANUAL: data.pop(CONF_MANUAL, False),
                CONF_SERVER_ID: str(data.pop(CONF_SERVER_ID, "")),
            }
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=data, options=options
            )

    async def async_setup(self) -> None:
        """Set up SpeedTest."""
        try:
            self.api = await self.hass.async_add_executor_job(speedtest.Speedtest)
            await self.hass.async_add_executor_job(self.update_servers)
        except speedtest.SpeedtestException as err:
            raise ConfigEntryNotReady from err

        async def request_update(call):
            """Request update."""
            await self.async_request_refresh()

        await self.async_set_options()

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
