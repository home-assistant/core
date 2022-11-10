"""Define a PurpleAir DataUpdateCoordinator."""
from __future__ import annotations

from datetime import timedelta

from aiopurpleair import API
from aiopurpleair.errors import PurpleAirError
from aiopurpleair.models.sensors import GetSensorsResponse

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SENSOR_INDEX, DOMAIN, LOGGER

DEFAULT_UPDATE_INTERVAL = timedelta(minutes=2)

SENSOR_FIELDS_TO_RETRIEVE = [
    "0.3_um_count",
    "0.5_um_count",
    "1.0_um_count",
    "10.0_um_count",
    "2.5_um_count",
    "5.0_um_count",
    "altitude",
    "firmware_version",
    "hardware",
    "humidity",
    "latitude",
    "location_type",
    "longitude",
    "model",
    "name",
    "pm1.0",
    "pm10.0",
    "pm2.5",
    "pressure",
    "rssi",
    "temperature",
    "uptime",
    "voc",
]


class PurpleAirDataUpdateCoordinator(DataUpdateCoordinator[GetSensorsResponse]):
    """Define a PurpleAir-specific coordinator."""

    def __init__(self, hass: HomeAssistant, api_key: str) -> None:
        """Initialize."""
        self._api = API(api_key, session=aiohttp_client.async_get_clientsession(hass))

        # Set the initial list of sensor indices to track by examining all PurpleAir
        # config entries that utilize the same API key that was passed to this
        # coordinator:
        self._sensor_indices: list[int] = [
            entry.data[CONF_SENSOR_INDEX]
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.data[CONF_API_KEY] == api_key
        ]

        super().__init__(
            hass,
            LOGGER,
            name=str(self._sensor_indices),
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )

    @callback
    def _async_update_coordinator_name(self) -> None:
        """Update the coordinator name with the latest tracked sensor indices."""
        self.name = str(self._sensor_indices)

    async def _async_update_data(self) -> GetSensorsResponse:
        """Get the latest sensor information."""
        try:
            return await self._api.sensors.async_get_sensors(
                SENSOR_FIELDS_TO_RETRIEVE, sensor_indices=self._sensor_indices
            )
        except PurpleAirError as err:
            raise UpdateFailed(f"Error while fetching data: {err}") from err

    @callback
    def async_track_sensor_index(self, sensor_index: int) -> None:
        """Track a new PurpleAir sensor index."""
        self._sensor_indices.append(sensor_index)
        self._async_update_coordinator_name()

    @callback
    def async_untrack_sensor_index(self, sensor_index: int) -> bool:
        """Track a new PurpleAir sensor index.

        Returns a bool indicating whether the coordinator is still tracking indices.
        """
        self._sensor_indices.remove(sensor_index)
        self._async_update_coordinator_name()
        return len(self._sensor_indices) > 0
