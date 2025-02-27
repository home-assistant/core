"""The WeatherflowCloud integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from weatherflow4py.api import WeatherFlowRestAPI
from weatherflow4py.models.ws.obs import WebsocketObservation
from weatherflow4py.models.ws.types import EventType
from weatherflow4py.models.ws.websocket_request import (
    ListenStartMessage,
    RapidWindListenStartMessage,
)
from weatherflow4py.models.ws.websocket_response import EventDataRapidWind, RapidWindWS
from weatherflow4py.ws import WeatherFlowWebsocketAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER
from .coordinator import (
    WeatherFlowCloudDataCallbackCoordinator,
    WeatherFlowCloudUpdateCoordinatorREST,
)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.WEATHER]


@dataclass
class WeatherFlowCoordinators:
    """Data Class for Entry Data."""

    rest: WeatherFlowCloudUpdateCoordinatorREST
    wind: WeatherFlowCloudDataCallbackCoordinator[
        EventDataRapidWind, RapidWindListenStartMessage, RapidWindWS
    ]
    observation: WeatherFlowCloudDataCallbackCoordinator[
        WebsocketObservation, ListenStartMessage, WebsocketObservation
    ]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WeatherFlowCloud from a config entry."""

    LOGGER.debug("Initializing WeatherFlowCloudDataUpdateCoordinatorREST coordinator")

    rest_api = WeatherFlowRestAPI(
        api_token=entry.data[CONF_API_TOKEN], session=async_get_clientsession(hass)
    )

    stations = await rest_api.async_get_stations()

    # Define Rest Coordinator
    rest_data_coordinator = WeatherFlowCloudUpdateCoordinatorREST(
        hass=hass, rest_api=rest_api, stations=stations
    )

    # Initialize the stations
    await rest_data_coordinator.async_config_entry_first_refresh()

    # Construct Websocket Coordinators
    LOGGER.debug(
        "Initializing WeatherFlowCloudDataUpdateCoordinatorWebsocketWind coordinator"
    )
    websocket_device_ids = rest_data_coordinator.device_ids

    # Build API once
    websocket_api = WeatherFlowWebsocketAPI(
        access_token=entry.data[CONF_API_TOKEN], device_ids=websocket_device_ids
    )

    websocket_observation_coordinator = WeatherFlowCloudDataCallbackCoordinator[
        WebsocketObservation, WebsocketObservation, ListenStartMessage
    ](
        hass=hass,
        rest_api=rest_api,
        websocket_api=websocket_api,
        stations=stations,
        listen_request_type=ListenStartMessage,
        event_type=EventType.OBSERVATION,
    )

    websocket_wind_coordinator = WeatherFlowCloudDataCallbackCoordinator[
        EventDataRapidWind, EventDataRapidWind, RapidWindListenStartMessage
    ](
        hass=hass,
        stations=stations,
        rest_api=rest_api,
        websocket_api=websocket_api,
        listen_request_type=RapidWindListenStartMessage,
        event_type=EventType.RAPID_WIND,
    )

    # Run setup method.
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
