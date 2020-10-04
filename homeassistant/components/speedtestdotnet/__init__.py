"""Support for testing internet speed via Speedtest.net."""
from datetime import timedelta
import logging

import speedtest
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS,
    CONF_SCAN_INTERVAL,
    EVENT_HOMEASSISTANT_STARTED,
)
from homeassistant.core import CoreState, callback
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_MANUAL,
    CONF_SERVER_ID,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SERVER,
    DOMAIN,
    SENSOR_TYPES,
    SPEED_TEST_SERVICE,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_SERVER_ID): cv.positive_int,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=timedelta(minutes=DEFAULT_SCAN_INTERVAL)
                ): cv.positive_time_period,
                vol.Optional(CONF_MANUAL, default=False): cv.boolean,
                vol.Optional(
                    CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)
                ): vol.All(cv.ensure_list, [vol.In(list(SENSOR_TYPES))]),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def server_id_valid(server_id):
    """Check if server_id is valid."""
    try:
        api = speedtest.Speedtest()
        api.get_servers([int(server_id)])
    except (speedtest.ConfigRetrievalError, speedtest.NoMatchedServers):
        return False

    return True


async def async_setup(hass, config):
    """Import integration from config."""

    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )
    return True


async def async_setup_entry(hass, config_entry):
    """Set up the Speedtest.net component."""
    coordinator = SpeedTestDataCoordinator(hass, config_entry)
    await coordinator.async_setup()

    async def _enable_scheduled_speedtests(*_):
        """Activate the data update coordinator."""
        coordinator.update_interval = timedelta(
            minutes=config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        await coordinator.async_refresh()

    if not config_entry.options[CONF_MANUAL]:
        if hass.state == CoreState.running:
            await _enable_scheduled_speedtests()
            if not coordinator.last_update_success:
                raise ConfigEntryNotReady
        else:
            # Running a speed test during startup can prevent
            # integrations from being able to setup because it
            # can saturate the network interface.
            hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, _enable_scheduled_speedtests
            )

    hass.data[DOMAIN] = coordinator

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload SpeedTest Entry from config_entry."""
    hass.services.async_remove(DOMAIN, SPEED_TEST_SERVICE)

    hass.data[DOMAIN].async_unload()

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
        self._unsub_update_listener = None
        super().__init__(
            self.hass,
            _LOGGER,
            name=DOMAIN,
            update_method=self.async_update,
        )

    def update_servers(self):
        """Update list of test servers."""
        try:
            server_list = self.api.get_servers()
        except speedtest.ConfigRetrievalError:
            return

        self.servers[DEFAULT_SERVER] = {}
        for server in sorted(
            server_list.values(),
            key=lambda server: server[0]["country"] + server[0]["sponsor"],
        ):
            self.servers[
                f"{server[0]['country']} - {server[0]['sponsor']} - {server[0]['name']}"
            ] = server[0]

    def update_data(self):
        """Get the latest data from speedtest.net."""
        self.update_servers()

        self.api.closest.clear()
        if self.config_entry.options.get(CONF_SERVER_ID):
            server_id = self.config_entry.options.get(CONF_SERVER_ID)
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
        except (speedtest.ConfigRetrievalError, speedtest.NoMatchedServers) as err:
            raise UpdateFailed from err

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

    async def async_setup(self):
        """Set up SpeedTest."""
        try:
            self.api = await self.hass.async_add_executor_job(speedtest.Speedtest)
        except speedtest.ConfigRetrievalError as err:
            raise ConfigEntryNotReady from err

        async def request_update(call):
            """Request update."""
            await self.async_request_refresh()

        await self.async_set_options()

        await self.hass.async_add_executor_job(self.update_servers)

        self.hass.services.async_register(DOMAIN, SPEED_TEST_SERVICE, request_update)

        self._unsub_update_listener = self.config_entry.add_update_listener(
            options_updated_listener
        )

    @callback
    def async_unload(self):
        """Unload the coordinator."""
        if not self._unsub_update_listener:
            return
        self._unsub_update_listener()
        self._unsub_update_listener = None


async def options_updated_listener(hass, entry):
    """Handle options update."""
    if entry.options[CONF_MANUAL]:
        hass.data[DOMAIN].update_interval = None
        return

    hass.data[DOMAIN].update_interval = timedelta(
        minutes=entry.options[CONF_SCAN_INTERVAL]
    )
    await hass.data[DOMAIN].async_request_refresh()
