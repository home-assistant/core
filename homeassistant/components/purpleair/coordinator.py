"""Define a PurpleAir DataUpdateCoordinator."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

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
from .const import DOMAIN, LOGGER, SENSOR_FIELDS_TO_RETRIEVE

UPDATE_INTERVAL = timedelta(minutes=2)

type PurpleAirConfigEntry = ConfigEntry[PurpleAirDataUpdateCoordinator]


def async_get_api(hass: HomeAssistant, api_key: str) -> API:
    """Create aiopurpleair API object."""
    session = aiohttp_client.async_get_clientsession(hass)
    return API(api_key, session=session)


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
            update_interval=UPDATE_INTERVAL,
        )
        self._api = async_get_api(hass, entry.data[CONF_API_KEY])

    async def _async_update_data(self) -> GetSensorsResponse:
        """Get the latest sensor information."""
        index_list = ConfigSchema.async_get_sensor_index_list(
            dict(self.config_entry.options)
        )
        assert index_list is not None and len(index_list) > 0, (
            "No sensor indexes found in configuration"
        )

        read_keys_list = ConfigSchema.async_get_sensor_read_key_list(
            dict(self.config_entry.options)
        )
        if read_keys_list is None or len(read_keys_list) == 0:
            read_keys_list = None

        try:
            return await self._api.sensors.async_get_sensors(
                SENSOR_FIELDS_TO_RETRIEVE,
                sensor_indices=index_list,
                read_keys=read_keys_list,
            )
        except InvalidApiKeyError as err:
            raise ConfigEntryAuthFailed("Invalid API key") from err
        except PurpleAirError as err:
            raise UpdateFailed(f"Error while fetching data: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error while fetching data: {err}") from err

    def async_get_map_url(self, sensor_index: int) -> str:
        """Get the map URL for a sensor index."""
        return self._api.get_map_url(sensor_index)

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
