"""Weatherflow Data Update Coordinator definition."""
import asyncio
from datetime import timedelta
from random import randrange
from types import MappingProxyType
from typing import Any

from pyweatherflow_forecast import (
    WeatherFlow,
    WeatherFlowForecastBadRequest,
    WeatherFlowForecastDaily,
    WeatherFlowForecastData,
    WeatherFlowForecastHourly,
    WeatherFlowForecastInternalServerError,
    WeatherFlowForecastUnauthorized,
    WeatherFlowForecastWongStationId,
    WeatherFlowSensorData,
    WeatherFlowStationData,
)
from pyweatherflowudp.client import EVENT_DEVICE_DISCOVERED, WeatherFlowListener
from pyweatherflowudp.device import EVENT_LOAD_COMPLETE, WeatherFlowDevice
from pyweatherflowudp.errors import ListenerError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    HomeAssistantError,
    Unauthorized,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    _LOGGER,
    CONF_CLOUD_SENSORS,
    CONF_LOCAL_SENSORS,
    CONF_STATION_ID,
    DOMAIN,
    format_dispatch_call,
)


class WeatherFlowCloudData:
    """Class to hold/store."""

    def __init__(
        self, hass: HomeAssistant, config: MappingProxyType[str, Any], add_sensors=False
    ) -> None:
        """Iniitalize cloud data interface."""
        self.current_weather_data: WeatherFlowForecastData = {}
        self.daily_forecast: WeatherFlowForecastDaily = []
        self.hourly_forecast: WeatherFlowForecastHourly = []
        self.sensor_data: WeatherFlowSensorData = {}
        self.station_data: WeatherFlowStationData = {}
        self._weather_data = WeatherFlow(
            config[CONF_STATION_ID],
            config[CONF_API_TOKEN],
            elevation=hass.config.elevation,
            session=async_get_clientsession(hass),
        )
        self._add_sensors = add_sensors

    async def fetch_data(self, fetch_forecast: bool = True) -> None:
        """Fetch the data that we should fetch."""

        await asyncio.gather(
            self.fetch_forecast_data() if fetch_forecast else asyncio.sleep(0),
            self.fetch_station_info(),
            self.fetch_sensor_data() if self._add_sensors else asyncio.sleep(0),
        )

        # class WeatherFlowData:

    # class WeatherFlowForecastWeatherData:
    #     """Keep data for WeatherFlow Forecast entity data."""
    #
    #     def __init__(
    #         self,
    #         hass: HomeAssistant,
    #         config: MappingProxyType[str, Any],
    #         add_cloud_sensors: bool = False,
    #     ) -> None:
    #         """Initialise the weather entity data."""
    #         self.hass = hass
    #         self._config = config
    #         self._add_sensors = add_cloud_sensors
    #         self._weather_data: WeatherFlow
    #         self.current_weather_data: WeatherFlowForecastData = {}
    #         self.daily_forecast: WeatherFlowForecastDaily = []
    #         self.hourly_forecast: WeatherFlowForecastHourly = []
    #         self.sensor_data: WeatherFlowSensorData = {}
    #         self.station_data: WeatherFlowStationData = {}
    #
    # def initialize_data(self) -> bool:
    #     """Establish connection to API."""
    #
    #     self._weather_data = WeatherFlow(
    #         self._config[CONF_STATION_ID],
    #         self._config[CONF_API_TOKEN],
    #         elevation=self.hass.config.elevation,
    #         session=async_get_clientsession(self.hass),
    #     )

    #         return True
    #
    async def fetch_station_info(self) -> None:
        """Fetch station information and update internal data structure."""
        self.station_data = await self._weather_data.async_get_station()

    async def fetch_forecast_data(self) -> None:
        """Retrieve weather forecast."""
        try:
            response: WeatherFlowForecastData = (
                await self._weather_data.async_get_forecast()
            )

        except WeatherFlowForecastWongStationId as unauthorized:
            _LOGGER.debug(unauthorized)
            raise Unauthorized from unauthorized
        except WeatherFlowForecastBadRequest as err:
            _LOGGER.debug(err)
            raise err
        except WeatherFlowForecastUnauthorized as unauthorized:
            _LOGGER.debug(unauthorized)
            raise Unauthorized from unauthorized
        except WeatherFlowForecastInternalServerError as notreadyerror:
            _LOGGER.debug(notreadyerror)
            raise ConfigEntryNotReady from notreadyerror

        if not response:
            raise CannotConnect()

        self.current_weather_data = response
        self.daily_forecast = response.forecast_daily
        self.hourly_forecast = response.forecast_hourly

    async def fetch_sensor_data(self) -> None:
        """Fetch sensor data."""
        await self.fetch_station_info()
        try:
            self.sensor_data = await self._weather_data.async_fetch_sensor_data()
        except WeatherFlowForecastWongStationId as unauthorized:
            _LOGGER.debug(unauthorized)
            raise Unauthorized from unauthorized
        except WeatherFlowForecastBadRequest as err:
            _LOGGER.debug(err)
            raise err
        except WeatherFlowForecastUnauthorized as unauthorized:
            _LOGGER.debug(unauthorized)
            raise Unauthorized from unauthorized
        except WeatherFlowForecastInternalServerError as notreadyerror:
            _LOGGER.debug(notreadyerror)
            raise ConfigEntryNotReady from notreadyerror

        # if not resp or not station_info:
        #     raise CannotConnect()

    # async def fetch_data(self) -> Self:
    #     """Fetch data from API - (current weather and forecast)."""
    #
    #     try:
    #         _LOGGER.info("Fetching weather data")
    #         resp: WeatherFlowForecastData = (
    #             await self._weather_data.async_get_forecast()
    #         )
    #
    #     except WeatherFlowForecastWongStationId as unauthorized:
    #         _LOGGER.debug(unauthorized)
    #         raise Unauthorized from unauthorized
    #     except WeatherFlowForecastBadRequest as err:
    #         _LOGGER.debug(err)
    #         return False
    #     except WeatherFlowForecastUnauthorized as unauthorized:
    #         _LOGGER.debug(unauthorized)
    #         raise Unauthorized from unauthorized
    #     except WeatherFlowForecastInternalServerError as notreadyerror:
    #         _LOGGER.debug(notreadyerror)
    #         raise ConfigEntryNotReady from notreadyerror
    #
    #     if not resp:
    #         raise CannotConnect()
    #
    #     self.current_weather_data = resp
    #     self.daily_forecast = resp.forecast_daily
    #     self.hourly_forecast = resp.forecast_hourly
    #
    #     if self._add_sensors:
    #         try:
    #             resp: WeatherFlowForecastData = (
    #                 await self._weather_data.async_fetch_sensor_data()
    #             )
    #             station_info: WeatherFlowStationData = (
    #                 await self._weather_data.async_get_station()
    #             )
    #
    #         except WeatherFlowForecastWongStationId as unauthorized:
    #             _LOGGER.debug(unauthorized)
    #             raise Unauthorized from unauthorized
    #         except WeatherFlowForecastBadRequest as err:
    #             _LOGGER.debug(err)
    #             return False
    #         except WeatherFlowForecastUnauthorized as unauthorized:
    #             _LOGGER.debug(unauthorized)
    #             raise Unauthorized from unauthorized
    #         except WeatherFlowForecastInternalServerError as notreadyerror:
    #             _LOGGER.debug(notreadyerror)
    #             raise ConfigEntryNotReady from notreadyerror
    #
    #         if not resp or not station_info:
    #             raise CannotConnect()
    #         self.sensor_data = resp
    #         self.station_data = station_info
    #         # _LOGGER.debug(vars(self.sensor_data))
    #
    #     return self

    @property
    def add_sensors(self):
        """Property getter for sensor add state."""
        return self._add_sensors


class WeatherFlowHybridDataUpdateCoordinator(
    DataUpdateCoordinator["WeatherFlowForecastWeatherData"]
):
    """Class to manage fetching REST Based WeatherFlow Forecast data."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize global WeatherFlow forecast data updater."""

        # Store local variables
        self.hass = hass
        self.config_entry = config_entry

        self.local_client = WeatherFlowListener()
        self.cloud_client = WeatherFlowCloudData(hass, config_entry.data)

        self.cloud_enabled: bool = (
            self.config_entry.data.get(CONF_API_TOKEN) is not None
        ) and (self.config_entry.data.get(CONF_STATION_ID) is not None)

        update_interval = None
        if self.cloud_enabled:
            if config_entry.options[CONF_CLOUD_SENSORS]:
                update_interval = timedelta(minutes=randrange(1, 5))
            else:
                update_interval = timedelta(minutes=randrange(25, 35))

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
            always_update=(self.cloud_enabled is True),
        )

    async def start_clients(self):
        """Start local and remote clients as Appropriate."""

        if self.config_entry.options[CONF_LOCAL_SENSORS]:
            _LOGGER.info("Initializing Local UDP Client")
            await self._start_local_sensors()

        if (
            self.config_entry.data[CONF_API_TOKEN]
            and self.config_entry.data[CONF_STATION_ID]
        ):
            _LOGGER.info("Obtaining Station Data (REST)")
            await self.cloud_client.fetch_data()

    async def stop_clients(self):
        """Stop clients (in this case just the UDP)."""
        await self.local_client.stop_listening()

    # @property
    # def data(self):
    #     return self._cloud_client
    #
    # @data.setter
    # def data(self, value):
    #     self._cloud_client = value
    @property
    def add_cloud_sensors(self) -> bool:
        """Return cloud sensor status."""
        return self.cloud_client.add_sensors

    # async def _initialize_station_data(self):
    #     # Initialize station data
    #
    #     self.weatherflow_api = WeatherFlow(
    #         self.config_entry.data[CONF_STATION_ID],
    #         self.config_entry.data[CONF_API_TOKEN],
    #         session=async_create_clientsession(self.hass),
    #     )
    #     self.station_data = await self.weatherflow_api.async_get_station()

    # async def _start_cloud_forecast(self):
    #     forecast = await self.weatherflow_api.async_get_forecast()
    #     print(forecast)

    # async def _start_cloud_sensors(self):
    #     pass

    async def _start_local_sensors(self):
        """Enable local UDP sensors."""

        @callback
        def _async_device_discovered(device: WeatherFlowDevice) -> None:
            _LOGGER.debug("Found a device: %s", device)

            @callback
            def _async_add_device_if_started(device: WeatherFlowDevice):
                async_at_started(
                    self.hass,
                    callback(
                        lambda _: async_dispatcher_send(
                            self.hass, format_dispatch_call(self.config_entry), device
                        )
                    ),
                )

            self.config_entry.async_on_unload(
                device.on(
                    EVENT_LOAD_COMPLETE,
                    lambda _: _async_add_device_if_started(device),
                )
            )

        self.config_entry.async_on_unload(
            self.local_client.on(EVENT_DEVICE_DISCOVERED, _async_device_discovered)
        )

        try:
            await self.local_client.start_listening()
        except ListenerError as ex:
            raise ConfigEntryNotReady from ex

    async def _async_update_data(self) -> None:
        """Fetch data from WeatherFlow Forecast."""
        try:
            return await self.cloud_client.fetch_data()

        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err


class CannotConnect(HomeAssistantError):
    """Unable to connect to the web site."""
