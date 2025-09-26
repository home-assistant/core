"""Improved coordinator design with better type safety."""

from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Generic, TypeVar

from aiohttp import ClientResponseError
from weatherflow4py.api import WeatherFlowRestAPI
from weatherflow4py.models.rest.stations import StationsResponseREST
from weatherflow4py.models.rest.unified import WeatherFlowDataREST
from weatherflow4py.models.ws.obs import WebsocketObservation
from weatherflow4py.models.ws.types import EventType
from weatherflow4py.models.ws.websocket_request import (
    ListenStartMessage,
    RapidWindListenStartMessage,
)
from weatherflow4py.models.ws.websocket_response import (
    EventDataRapidWind,
    ObservationTempestWS,
    RapidWindWS,
)
from weatherflow4py.ws import WeatherFlowWebsocketAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.ssl import client_context

from .const import DOMAIN, LOGGER

T = TypeVar("T")


class BaseWeatherFlowCoordinator(DataUpdateCoordinator[dict[int, T]], ABC, Generic[T]):
    """Base class for WeatherFlow coordinators."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        rest_api: WeatherFlowRestAPI,
        stations: StationsResponseREST,
        update_interval: timedelta | None = None,
        always_update: bool = False,
    ) -> None:
        """Initialize Coordinator."""
        self._token = rest_api.api_token
        self._rest_api = rest_api
        self.stations = stations
        self.device_to_station_map = stations.device_station_map
        self.device_ids = list(stations.device_station_map.keys())

        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            always_update=always_update,
            update_interval=update_interval,
        )

    @abstractmethod
    def get_station_name(self, station_id: int) -> str:
        """Get station name for the given station ID."""


class WeatherFlowCloudUpdateCoordinatorREST(
    BaseWeatherFlowCoordinator[WeatherFlowDataREST]
):
    """Class to manage fetching REST Based WeatherFlow Forecast data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        rest_api: WeatherFlowRestAPI,
        stations: StationsResponseREST,
    ) -> None:
        """Initialize global WeatherFlow forecast data updater."""
        super().__init__(
            hass,
            config_entry,
            rest_api,
            stations,
            update_interval=timedelta(seconds=60),
            always_update=True,
        )

    async def _async_update_data(self) -> dict[int, WeatherFlowDataREST]:
        """Update rest data."""
        try:
            async with self._rest_api:
                return await self._rest_api.get_all_data()
        except ClientResponseError as err:
            if err.status == 401:
                raise ConfigEntryAuthFailed(err) from err
            raise UpdateFailed(f"Update failed: {err}") from err

    def get_station(self, station_id: int) -> WeatherFlowDataREST:
        """Return station for id."""
        return self.data[station_id]

    def get_station_name(self, station_id: int) -> str:
        """Return station name for id."""
        return self.data[station_id].station.name


class BaseWebsocketCoordinator(
    BaseWeatherFlowCoordinator[dict[int, T | None]], ABC, Generic[T]
):
    """Base class for websocket coordinators."""

    _event_type: EventType

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        rest_api: WeatherFlowRestAPI,
        websocket_api: WeatherFlowWebsocketAPI,
        stations: StationsResponseREST,
    ) -> None:
        """Initialize Coordinator."""
        super().__init__(
            hass=hass, config_entry=config_entry, rest_api=rest_api, stations=stations
        )

        self.websocket_api = websocket_api

        # Configure the websocket data structure
        self._ws_data: dict[int, dict[int, T | None]] = {
            station: dict.fromkeys(devices)
            for station, devices in self.stations.station_device_map.items()
        }

    async def async_setup(self) -> None:
        """Set up the websocket connection."""
        await self.websocket_api.connect(client_context())
        self.websocket_api.register_callback(
            message_type=self._event_type,
            callback=self._handle_websocket_message,
        )

        # Subscribe to messages for all devices
        for device_id in self.device_ids:
            message = self._create_listen_message(device_id)
            await self.websocket_api.send_message(message)

    @abstractmethod
    def _create_listen_message(self, device_id: int):
        """Create the appropriate listen message for this coordinator type."""

    @abstractmethod
    async def _handle_websocket_message(self, data) -> None:
        """Handle incoming websocket data."""

    def get_station(self, station_id: int):
        """Return station for id."""
        return self.stations.stations[station_id]

    def get_station_name(self, station_id: int) -> str:
        """Return station name for id."""
        return self.stations.station_map[station_id].name or ""


class WeatherFlowWindCoordinator(BaseWebsocketCoordinator[EventDataRapidWind]):
    """Coordinator specifically for rapid wind data."""

    _event_type = EventType.RAPID_WIND

    def _create_listen_message(self, device_id: int) -> RapidWindListenStartMessage:
        """Create rapid wind listen message."""
        return RapidWindListenStartMessage(device_id=str(device_id))

    async def _handle_websocket_message(self, data: RapidWindWS) -> None:
        """Handle rapid wind websocket data."""
        device_id = data.device_id
        station_id = self.device_to_station_map[device_id]

        # Extract the observation data from the RapidWindWS message
        self._ws_data[station_id][device_id] = data.ob
        self.async_set_updated_data(self._ws_data)


class WeatherFlowObservationCoordinator(BaseWebsocketCoordinator[WebsocketObservation]):
    """Coordinator specifically for observation data."""

    _event_type = EventType.OBSERVATION

    def _create_listen_message(self, device_id: int) -> ListenStartMessage:
        """Create observation listen message."""
        return ListenStartMessage(device_id=str(device_id))

    async def _handle_websocket_message(self, data: ObservationTempestWS) -> None:
        """Handle observation websocket data."""
        device_id = data.device_id
        station_id = self.device_to_station_map[device_id]

        # For observations, the data IS the observation
        self._ws_data[station_id][device_id] = data
        self.async_set_updated_data(self._ws_data)


# Type aliases for better readability
type WeatherFlowWindCallback = WeatherFlowWindCoordinator
type WeatherFlowObservationCallback = WeatherFlowObservationCoordinator
