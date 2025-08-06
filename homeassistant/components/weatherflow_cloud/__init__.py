"""The WeatherflowCloud integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from weatherflow4py.api import WeatherFlowRestAPI
from weatherflow4py.ws import WeatherFlowWebsocketAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER
from .coordinator import (
    WeatherFlowCloudUpdateCoordinatorREST,
    WeatherFlowObservationCoordinator,
    WeatherFlowWindCoordinator,
)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.WEATHER]


@dataclass
class WeatherFlowCoordinators:
    """Data Class for Entry Data."""

    rest: WeatherFlowCloudUpdateCoordinatorREST
    wind: WeatherFlowWindCoordinator
    observation: WeatherFlowObservationCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WeatherFlowCloud from a config entry."""

    LOGGER.debug("Initializing WeatherFlowCloudDataUpdateCoordinatorREST coordinator")

    rest_api = WeatherFlowRestAPI(
        api_token=entry.data[CONF_API_TOKEN], session=async_get_clientsession(hass)
    )

    stations = await rest_api.async_get_stations()

    # Define Rest Coordinator
    rest_data_coordinator = WeatherFlowCloudUpdateCoordinatorREST(
        hass=hass, config_entry=entry, rest_api=rest_api, stations=stations
    )

    # Initialize the stations
    await rest_data_coordinator.async_config_entry_first_refresh()

    # Construct Websocket Coordinators
    LOGGER.debug("Initializing websocket coordinators")
    websocket_device_ids = rest_data_coordinator.device_ids

    # Build API once
    websocket_api = WeatherFlowWebsocketAPI(
        access_token=entry.data[CONF_API_TOKEN], device_ids=websocket_device_ids
    )

    websocket_observation_coordinator = WeatherFlowObservationCoordinator(
        hass=hass,
        config_entry=entry,
        rest_api=rest_api,
        websocket_api=websocket_api,
        stations=stations,
    )

    websocket_wind_coordinator = WeatherFlowWindCoordinator(
        hass=hass,
        config_entry=entry,
        rest_api=rest_api,
        websocket_api=websocket_api,
        stations=stations,
    )

    # Run setup method
    await asyncio.gather(
        websocket_wind_coordinator.async_setup(),
        websocket_observation_coordinator.async_setup(),
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = WeatherFlowCoordinators(
        rest_data_coordinator,
        websocket_wind_coordinator,
        websocket_observation_coordinator,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Websocket disconnect handler
    async def _async_disconnect_websocket() -> None:
        await websocket_api.stop_all_listeners()
        await websocket_api.close()

    # Register a websocket shutdown handler
    entry.async_on_unload(_async_disconnect_websocket)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
