"""Define a PurpleAir DataUpdateCoordinator."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Final

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

UPDATE_INTERVAL: Final[int] = 5


class PurpleAirDataUpdateCoordinator(DataUpdateCoordinator[GetSensorsResponse]):
    """Define a PurpleAir-specific coordinator."""

    config_entry: PurpleAirConfigEntry

    def __init__(self, hass: HomeAssistant, entry: PurpleAirConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=timedelta(minutes=UPDATE_INTERVAL),
            always_update=True,
        )
        self._api = API(
            entry.data[CONF_API_KEY],
            session=aiohttp_client.async_get_clientsession(hass),
        )

    def async_get_map_url(self, sensor_index: int) -> str:
        """Get map URL."""
        return self._api.get_map_url(sensor_index)

    async def _async_update_data(self) -> GetSensorsResponse:
        """Get the latest sensor information."""
        index_list: list[int] = [
            int(subentry.data[CONF_SENSOR_INDEX])
            for subentry in self.config_entry.subentries.values()
        ]
        read_key_list: list[str] | None = [
            str(subentry.data[CONF_SENSOR_READ_KEY])
            for subentry in self.config_entry.subentries.values()
            if subentry.data.get(CONF_SENSOR_READ_KEY) is not None
        ] or None
        if TYPE_CHECKING:
            assert index_list is not None and len(index_list) > 0

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
