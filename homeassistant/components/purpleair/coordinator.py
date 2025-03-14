"""PurpleAir data update coordinator."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Final

from aiopurpleair import API
from aiopurpleair.errors import InvalidApiKeyError, PurpleAirError
from aiopurpleair.models.sensors import GetSensorsResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import aiohttp_client, device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .config_schema import ConfigSchema
from .const import (
    CONF_SENSOR_INDEX,
    CONF_SENSOR_READ_KEY,
    DOMAIN,
    LOGGER,
    SENSOR_FIELDS_TO_RETRIEVE,
)

type PurpleAirConfigEntry = ConfigEntry[PurpleAirDataUpdateCoordinator]

UPDATE_INTERVAL: Final[int] = 2


def async_get_api(hass: HomeAssistant, api_key: str) -> API:
    """Create aiopurpleair API object."""
    session = aiohttp_client.async_get_clientsession(hass)
    return API(api_key, session=session)


type PurpleAirConfigEntry = ConfigEntry[PurpleAirDataUpdateCoordinator]


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
        )
        self._api = async_get_api(hass, entry.data[CONF_API_KEY])

    async def _async_update_data(self) -> GetSensorsResponse:
        """Update sensor data."""
        index_list: list[int] = [
            int(subentry.data[CONF_SENSOR_INDEX])
            for subentry in self.config_entry.subentries.values()
        ]
        read_key_list: list[str] | None = [
            str(subentry.data[CONF_SENSOR_READ_KEY])
            for subentry in self.config_entry.subentries.values()
            if CONF_SENSOR_READ_KEY in subentry.data
        ] or None

        if index_list is None or len(index_list) == 0:
            raise UpdateFailed("No sensors found in configuration")

        try:
            return await self._api.sensors.async_get_sensors(
                SENSOR_FIELDS_TO_RETRIEVE,
                sensor_indices=index_list,
                read_keys=read_key_list,
            )
        except InvalidApiKeyError as err:
            raise ConfigEntryAuthFailed("Invalid API key") from err
        except PurpleAirError as err:
            raise UpdateFailed(f"Error while fetching data: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error while fetching data: {err}") from err

    def async_get_map_url(self, sensor_index: int) -> str:
        """Get map URL."""
        return self._api.get_map_url(sensor_index)

    # TODO: Update for new schema # pylint: disable=fixme
    def async_delete_orphans_from_device_registry(
        self, options: dict[str, Any] | None = None
    ) -> None:
        """Delete unreferenced sensors from the device registry."""
        device_registry = dr.async_get(self.hass)
        device_list = dr.async_entries_for_config_entry(
            device_registry, self.config_entry.entry_id
        )
        if not options:
            options = dict(self.config_entry.options)
        index_list = ConfigSchema.async_get_sensor_index_list(options)

        if not device_list or not index_list:
            return

        for device in device_list:
            identifiers = (
                int(identifier[1])
                for identifier in device.identifiers
                if identifier[0] == DOMAIN
            )
            sensor_index = next(identifiers, None)
            if sensor_index is None or sensor_index not in index_list:
                device_registry.async_remove_device(device.id)
