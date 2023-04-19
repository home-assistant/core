"""go-e Charger Cloud main integration file."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, CONF_HOST, CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CHARGERS_API,
    CONF_CHARGERS,
    DOMAIN,
    INIT_STATE,
    UNSUB_OPTIONS_UPDATE_LISTENER,
)
from .controller import ping_charger
from .state import StateFetcher, init_state

_LOGGER: logging.Logger = logging.getLogger(__name__)

MIN_UPDATE_INTERVAL: timedelta = timedelta(seconds=10)
MAX_UPDATE_INTERVAL: timedelta = timedelta(seconds=60000)
DEFAULT_UPDATE_INTERVAL: timedelta = timedelta(seconds=10)

PLATFORMS: list[str] = [
    SENSOR_DOMAIN,
]

# Configuration validation
CONFIG_SCHEMA: vol.Schema = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CHARGERS, default=[]): vol.All(
                    [
                        cv.ensure_list,
                        vol.All(
                            {
                                vol.Required(CONF_NAME): vol.All(cv.string),
                                vol.Required(CONF_HOST): vol.All(cv.string),
                                vol.Required(CONF_API_TOKEN): vol.All(cv.string),
                            }
                        ),
                    ],
                ),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_UPDATE_INTERVAL
                ): vol.All(
                    cv.time_period,
                    vol.Clamp(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL),
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def _setup_coordinator(
    hass: HomeAssistant,
    scan_interval: timedelta,
    coordinator_name: str,
) -> DataUpdateCoordinator:
    """Initialize the coordinator with empty state."""
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


def _setup_apis(hass: HomeAssistant, config: ConfigType) -> dict:
    """Initialize the API and save the reference in the state."""
    chargers_api: dict = {}

    if DOMAIN in config:
        hass.data[DOMAIN] = {}
        chargers: list[list[dict]] = config[DOMAIN].get(CONF_CHARGERS, [])

        for charger in chargers:
            name: str = charger[0][CONF_NAME]
            url: str = charger[0][CONF_HOST]
            token: str = charger[0][CONF_API_TOKEN]

            _LOGGER.debug("Configuring API for the charger=%s", name)
            chargers_api[name] = init_state(name, url, token)

    else:
        _LOGGER.warning("Missing %s entry in the config", DOMAIN)

    _LOGGER.debug("Configured charger APIs=%s", chargers_api)

    return chargers_api


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """
    Set up a charger defined via the UI. This includes.

    - setup of the API
    - coordinator
    - sensors
    """
    data = dict(config_entry.data)
    entry_id = config_entry.entry_id

    _LOGGER.debug(
        "Setting up an entry with id=%s",
        entry_id,
    )

    # scan interval is provided as an integer, but has to be an interval
    scan_interval: timedelta = timedelta(seconds=data[CONF_SCAN_INTERVAL])
    name: str = data[CONF_NAME]
    url: str = data[CONF_HOST]
    token: str = data[CONF_API_TOKEN]

    _LOGGER.debug("Configuring API for the charger=%s", entry_id)
    hass.data[DOMAIN][INIT_STATE][CHARGERS_API][entry_id] = init_state(name, url, token)

    # handle platform not ready
    await ping_charger(hass, entry_id)

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
        hass.data[DOMAIN][INIT_STATE][CHARGERS_API].pop(entry_id)

    _LOGGER.debug("Unloaded the entry=%s", entry_id)

    return unload_ok


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up go-e Charger Cloud platforms and services."""

    _LOGGER.debug("Setting up the go-e Charger Cloud integration")

    hass.data[DOMAIN] = hass.data[DOMAIN] if DOMAIN in hass.data else {}
    domain_config: dict = config[DOMAIN] if DOMAIN in config else {}

    scan_interval: timedelta = DEFAULT_UPDATE_INTERVAL
    chargers_api: dict = _setup_apis(hass, config)

    hass.data[DOMAIN][INIT_STATE] = {
        CHARGERS_API: chargers_api,
        UNSUB_OPTIONS_UPDATE_LISTENER: {},
    }

    charger_names = [
        charger[0][CONF_NAME] for charger in domain_config.get(CONF_CHARGERS, [])
    ]

    for charger_name in charger_names:
        # handle platform not ready
        await ping_charger(hass, charger_name)
        await _setup_coordinator(
            hass,
            scan_interval,
            f"{charger_name}_coordinator",
        ).async_config_entry_first_refresh()

    # load all platforms
    for platform in PLATFORMS:
        hass.async_create_task(
            async_load_platform(
                hass,
                platform,
                DOMAIN,
                {
                    CONF_CHARGERS: charger_names,
                },
                config,
            )
        )

    _LOGGER.debug("Setup for the go-e Charger Cloud integration completed")

    return True
