"""PurpleAir data update coordinator."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from aiopurpleair import API
from aiopurpleair.errors import InvalidApiKeyError, PurpleAirError
from aiopurpleair.models.sensors import GetSensorsResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SENSOR_INDEX, CONF_SENSOR_READ_KEY, LOGGER, SENSOR_FIELDS_ALL

type PurpleAirConfigEntry = ConfigEntry[PurpleAirDataUpdateCoordinator]

EMPTY_RESPONSE: Final[str] = (
    '{"api_version":"","time_stamp":0,"data_time_stamp":0,"max_age":0,"firmware_default_version":"","fields":["sensor_index","name","location_type","model","hardware","firmware_version","rssi","uptime","latitude","longitude","altitude","humidity","temperature","pressure","voc","pm1.0","pm2.5","pm10.0","0.3_um_count","0.5_um_count","1.0_um_count","2.5_um_count","5.0_um_count","10.0_um_count"],"location_types":["outside","inside"],"data":[[0,"",0,"","","",0,0,0.0,0.0,0,0,0,0.0,null,0.0,0.0,0.0,0,0,0,0,0,0]]}'
)
UPDATE_INTERVAL: Final[int] = 2


class PurpleAirDataUpdateCoordinator(DataUpdateCoordinator[GetSensorsResponse]):
    """Data update coordinator."""

    config_entry: PurpleAirConfigEntry

    def __init__(self, hass: HomeAssistant, entry: PurpleAirConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=timedelta(UPDATE_INTERVAL),
            always_update=True,
        )
        self._api = API(
            entry.data[CONF_API_KEY],
            session=aiohttp_client.async_get_clientsession(hass),
        )
        self._empty_response = GetSensorsResponse.model_validate_json(EMPTY_RESPONSE)

    def async_get_map_url(self, sensor_index: int) -> str:
        """Get map URL."""
        return self._api.get_map_url(sensor_index)

    async def _async_update_data(self) -> GetSensorsResponse:
        """Update sensor data."""
        index_list: list[int] = [
            int(subentry.data[CONF_SENSOR_INDEX])
            for subentry in self.config_entry.subentries.values()
        ]
        read_key_list: list[str] | None = [
            str(subentry.data[CONF_SENSOR_READ_KEY])
            for subentry in self.config_entry.subentries.values()
            if subentry.data.get(CONF_SENSOR_READ_KEY) is not None
        ] or None

        # TODO: Calling coordinator.async_config_entry_first_refresh() in init:async_setup_entry() will try to load sensors when none have been configured? # pylint: disable=fixme
        # If async_config_entry_first_refresh() is not called then new sensor values never gets loaded after creating a sensor subentry
        if index_list is None or len(index_list) == 0:
            LOGGER.warning("No sensors in configuration")
            return self._empty_response

        try:
            return await self._api.sensors.async_get_sensors(
                SENSOR_FIELDS_ALL,
                sensor_indices=index_list,
                read_keys=read_key_list,
            )
        except InvalidApiKeyError as err:
            raise ConfigEntryAuthFailed(f"InvalidApiKeyError: {err}") from err
        except PurpleAirError as err:
            raise UpdateFailed(f"PurpleAirError: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Exception: {err}") from err
