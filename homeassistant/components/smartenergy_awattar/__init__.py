"""Awattar integration."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
import logging

import aiohttp
from awattar_api.awattar_api import AwattarApi
import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    API,
    AWATTAR_API_URL,
    AWATTAR_COORDINATOR,
    CONF_COUNTRY,
    CONF_COUNTRY_LIST,
    DOMAIN,
    INIT_STATE,
    UNSUB_OPTIONS_UPDATE_LISTENER,
)
from .state import StateFetcher, init_state

_LOGGER: logging.Logger = logging.getLogger(__name__)

MIN_UPDATE_INTERVAL: timedelta = timedelta(seconds=10)
DEFAULT_UPDATE_INTERVAL: timedelta = timedelta(seconds=10)

PLATFORMS: list[str] = [
    SENSOR_DOMAIN,
]

# Configuration validation
CONFIG_SCHEMA: vol.Schema = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_COUNTRY): vol.In(sorted(CONF_COUNTRY_LIST)),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_UPDATE_INTERVAL
                ): vol.All(cv.time_period, vol.Clamp(min=MIN_UPDATE_INTERVAL)),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def ping_awattar(hass: HomeAssistant) -> None:
    """Make a call to Awattar. If it fails raise an error."""

    try:
        api: AwattarApi = hass.data[DOMAIN][INIT_STATE][API]
        await hass.async_add_executor_job(api.get_electricity_price)
    except (aiohttp.ClientError, RuntimeError) as ex:
        raise ConfigEntryNotReady(ex) from ex


def _setup_coordinator(
    hass: HomeAssistant,
    scan_interval: timedelta,
    coordinator_name: str,
) -> DataUpdateCoordinator:
    _LOGGER.debug("Configuring coordinator=%s", coordinator_name)

    state_fetcher: StateFetcher = StateFetcher(hass)
    coordinator: DataUpdateCoordinator[dict] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=state_fetcher.fetch_states,
        update_interval=scan_interval,
    )
    state_fetcher.coordinator = coordinator
    hass.data[DOMAIN][coordinator_name] = coordinator

    return coordinator


def _setup_api(config: ConfigType) -> dict:
    awattar_api = {}

    country: str = config[DOMAIN].get(CONF_COUNTRY)
    _LOGGER.debug("Configuring Awattar API")
    awattar_api = init_state(AWATTAR_API_URL[country])
    _LOGGER.debug("Configured Awattar API")

    return awattar_api


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """
    Set up the Awattar defined via the UI.

    - setup of the API
    - coordinator
    - sensors.
    """
    data = dict(config_entry.data)
    entry_id = config_entry.entry_id

    _LOGGER.debug(
        "Setting up an entry with id=%s",
        entry_id,
    )

    # scan interval is provided as an integer, but has to be an interval
    scan_interval: timedelta = timedelta(seconds=data[CONF_SCAN_INTERVAL])
    country: str = data[CONF_COUNTRY]

    _LOGGER.debug("Configuring Awattar API")
    hass.data[DOMAIN][INIT_STATE] = init_state(AWATTAR_API_URL[country])

    # handle platform not ready
    await ping_awattar(hass)

    await _setup_coordinator(
        hass,
        scan_interval,
        f"{entry_id}_coordinator",
    ).async_config_entry_first_refresh()

    hass.data[DOMAIN][entry_id] = data

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    unsub_options_update_listener: Callable = config_entry.add_update_listener(
        options_update_listener
    )
    hass.data[DOMAIN][INIT_STATE][UNSUB_OPTIONS_UPDATE_LISTENER][
        entry_id
    ] = unsub_options_update_listener

    _LOGGER.debug("Entry setup for %s completed", entry_id)

    return True


async def options_update_listener(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    entry_id: str = config_entry.entry_id
    _LOGGER.debug("Unloading the entry=%s", entry_id)

    unloaded_platforms: list[tuple[list, str]] = [
        (
            await asyncio.gather(
                *[
                    hass.config_entries.async_forward_entry_unload(
                        config_entry, platform
                    )
                ]
            ),
            platform,
        )
        for platform in PLATFORMS
    ]
    unload_ok: bool = all(unloaded_platforms)

    # Remove options_update_listener.
    hass.data[DOMAIN][INIT_STATE][UNSUB_OPTIONS_UPDATE_LISTENER][entry_id]()

    # Remove config entry from the domain.
    if unload_ok:
        hass.data[DOMAIN][INIT_STATE] = {}

    _LOGGER.debug("Unloaded the entry=%s", entry_id)

    return unload_ok


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Awattar platforms and services."""

    _LOGGER.debug("Setting up the Awattar integration")

    hass.data[DOMAIN] = hass.data[DOMAIN] if DOMAIN in hass.data else {}
    scan_interval: timedelta = DEFAULT_UPDATE_INTERVAL

    hass.data[DOMAIN] = {INIT_STATE: {}}

    if DOMAIN in config:
        hass.data[DOMAIN][INIT_STATE] = _setup_api(config)

        # handle platform not ready
        await ping_awattar(hass)

        await _setup_coordinator(
            hass, scan_interval, AWATTAR_COORDINATOR
        ).async_refresh()

        # load all platforms
        for platform in PLATFORMS:
            hass.async_create_task(
                async_load_platform(
                    hass,
                    platform,
                    DOMAIN,
                    {},
                    config,
                )
            )
    else:
        _LOGGER.warning("Missing %s entry in the config", DOMAIN)

    _LOGGER.debug("Setup for the Awattar integration completed")

    return True
