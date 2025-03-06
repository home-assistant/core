"""Define a PurpleAir DataUpdateCoordinator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from aiopurpleair import API
from aiopurpleair.endpoints.sensors import NearbySensorResult
from aiopurpleair.errors import InvalidApiKeyError, PurpleAirError
from aiopurpleair.models.sensors import GetSensorsResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import aiohttp_client, device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_SENSOR_INDEX,
    CONF_SENSOR_LIST,
    CONF_SENSOR_READ_KEY,
    DOMAIN,
    LOGGER,
)

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

UPDATE_INTERVAL = timedelta(minutes=2)

type PurpleAirConfigEntry = ConfigEntry[PurpleAirDataUpdateCoordinator]

# Config schema:
# API Key: config_entry.data[CONF_API_KEY]
# Sensor list: config_entry.options[CONF_SENSOR_LIST] as list[dict[str, Any]]
#   Sensor index: CONF_SENSOR_INDEX as int
#   Sensor read key (for private sensors): CONF_SENSOR_READ_KEY as str
# Options:
#   Show sensor on map: config_entry.options[CONF_SHOW_ON_MAP] as bool
type SensorConfigList = list[dict[str, Any]]


@dataclass
class SensorInfo:
    """Sensor information class."""

    def __init__(self, index: int, name: str, id: str | None) -> None:
        """Initialize."""
        self.index = index
        self.name = name
        self.id = id


def async_get_api(hass: HomeAssistant, api_key: str) -> API:
    """Create aiopurpleair API object."""
    session = aiohttp_client.async_get_clientsession(hass)
    return API(api_key, session=session)


def async_get_sensor_list(options: dict[str, Any]) -> SensorConfigList:
    """Get sensor list from options."""
    sensor_list: SensorConfigList | None = options.get(CONF_SENSOR_LIST)
    if sensor_list is None:
        sensor_list = []
        options[CONF_SENSOR_LIST] = sensor_list
    return sensor_list


def async_get_sensor_index_list(options: dict[str, Any]) -> list[int] | None:
    """Get sensor index list from options."""
    index_list = async_get_list_from_sensor_list(
        async_get_sensor_list(options), CONF_SENSOR_INDEX
    )
    if index_list is None or len(index_list) == 0:
        return None
    return index_list


def async_get_sensor_read_key_list(options: dict[str, Any]) -> list[str] | None:
    """Get sensor read key list from options."""
    read_key_list = async_get_list_from_sensor_list(
        async_get_sensor_list(options), CONF_SENSOR_READ_KEY
    )
    if read_key_list is None or len(read_key_list) == 0:
        return None
    return read_key_list


def async_get_list_from_sensor_list(
    sensor_list: SensorConfigList, key: str
) -> list[Any] | None:
    """Get item key list from sensor list."""
    if sensor_list is None or len(sensor_list) == 0:
        return None
    return [sensor[key] for sensor in sensor_list if sensor.get(key)]


def async_add_sensor_to_sensor_list(
    options: dict[str, Any], sensor_index: int, read_key: str | None
) -> SensorConfigList:
    """Add sensor to options."""
    sensor_list = async_get_sensor_list(options)
    sensor_list.append(
        {CONF_SENSOR_INDEX: sensor_index, CONF_SENSOR_READ_KEY: read_key}
    )
    return sensor_list


def async_remove_sensor_from_sensor_list(
    options: dict[str, Any], sensor_index: int
) -> SensorConfigList:
    """Remove sensor from options."""
    sensor_list = async_get_sensor_list(options)
    new_list = [
        sensor for sensor in sensor_list if sensor[CONF_SENSOR_INDEX] != sensor_index
    ]
    sensor_list.clear()
    sensor_list.extend(new_list)
    return sensor_list


def async_get_sensor_nearby_sensors_list(
    nearby_sensor_results: list[NearbySensorResult],
) -> list[SensorInfo]:
    """Get SensorInfo list from NearbySensorResult list."""
    return [
        SensorInfo(
            index=int(result.sensor.sensor_index), name=str(result.sensor.name), id=None
        )
        for result in nearby_sensor_results
    ]


def async_get_sensor_device_info_list(
    hass: HomeAssistant, entry_id: str
) -> list[SensorInfo]:
    """Get SensorInfo list from device registry."""
    device_list = dr.async_entries_for_config_entry(dr.async_get(hass), entry_id)
    return [
        SensorInfo(
            index=next(
                int(identifier[1])
                for identifier in device.identifiers
                if identifier[0] == DOMAIN
            ),
            name=str(device.name),
            id=str(device.id),
        )
        for device in device_list
    ]


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
        index_list = async_get_sensor_index_list(dict(self.config_entry.options))
        assert index_list is not None and len(index_list) > 0, (
            "No sensor indexes found in configuration"
        )

        read_keys_list = async_get_sensor_read_key_list(dict(self.config_entry.options))
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

    def async_get_map_url(self, sensor_index: int) -> str:
        """Get the map URL for a sensor index."""
        return self._api.get_map_url(sensor_index)

    def async_delete_orphans_from_device_registry(self) -> None:
        """Delete unreferenced sensors from the device registry."""
        device_list = async_get_sensor_device_info_list(
            self.hass, self.config_entry.entry_id
        )
        if device_list is None or len(device_list) == 0:
            return

        index_list = async_get_sensor_index_list(dict(self.config_entry.options))
        if index_list is None or len(index_list) == 0:
            return

        device_registry = dr.async_get(self.hass)
        for device in device_list:
            if device.index not in index_list:
                if device.id is not None:
                    device_registry.async_remove_device(device.id)
