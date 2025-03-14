"""PurpleAir configuration schema."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_SENSOR_INDEX, CONF_SENSOR_READ_KEY, SCHEMA_VERSION

# TODO: Update for new schema # pylint: disable=fixme

# Config schema:
# API Key: config_entry.data[CONF_API_KEY / "api_key"]
# Sensor list: config_entry.options[CONF_SENSOR_LIST / "sensor_list"] as list[dict[str, Any]]
#   Sensor index: CONF_SENSOR_INDEX / "sensor_index" as int
#   Sensor read key (for private sensors): CONF_SENSOR_READ_KEY / "sensor_read_key" as str
# Options:
#   Show sensor on map: config_entry.options[CONF_SHOW_ON_MAP / "show_on_map"] as bool

type SensorConfigList = list[dict[str, Any]]

CONF_SENSOR_LIST: Final[str] = "sensor_list"


class ConfigSchema:
    """Configuration schema."""

    @staticmethod
    def async_get_sensor_list(options: dict[str, Any]) -> SensorConfigList:
        """Get sensor list from options."""
        sensor_list: SensorConfigList | None = options.get(CONF_SENSOR_LIST)
        if sensor_list is None:
            sensor_list = []
            options[CONF_SENSOR_LIST] = sensor_list
        return sensor_list

    @staticmethod
    def async_get_sensor_index_list(options: dict[str, Any]) -> list[int] | None:
        """Get sensor index list from options."""
        index_list = ConfigSchema.async_get_list_from_sensor_list(
            ConfigSchema.async_get_sensor_list(options), CONF_SENSOR_INDEX
        )
        if index_list is None or len(index_list) == 0:
            return None
        return index_list

    @staticmethod
    def async_get_sensor_read_key_list(options: dict[str, Any]) -> list[str] | None:
        """Get sensor read key list from options."""
        read_key_list = ConfigSchema.async_get_list_from_sensor_list(
            ConfigSchema.async_get_sensor_list(options), CONF_SENSOR_READ_KEY
        )
        if read_key_list is None or len(read_key_list) == 0:
            return None
        return read_key_list

    @staticmethod
    def async_get_list_from_sensor_list(
        sensor_list: SensorConfigList, key: str
    ) -> list[Any] | None:
        """Get item key list from sensor list."""
        if sensor_list is None or len(sensor_list) == 0:
            return None
        return [sensor[key] for sensor in sensor_list if sensor.get(key)]

    @staticmethod
    def async_add_sensor_to_sensor_list(
        options: dict[str, Any], sensor_index: int, read_key: str | None
    ) -> SensorConfigList:
        """Add sensor to options."""
        assert type(sensor_index) is int
        assert read_key is None or type(read_key) is str
        sensor_list = ConfigSchema.async_get_sensor_list(options)
        sensor_list.append(
            {CONF_SENSOR_INDEX: sensor_index, CONF_SENSOR_READ_KEY: read_key}
        )
        return sensor_list

    @staticmethod
    def async_remove_sensor_from_sensor_list(
        options: dict[str, Any], sensor_index: int
    ) -> SensorConfigList:
        """Remove sensor from options."""
        sensor_list = ConfigSchema.async_get_sensor_list(options)
        new_list = [
            sensor
            for sensor in sensor_list
            if sensor[CONF_SENSOR_INDEX] != sensor_index
        ]
        sensor_list.clear()
        sensor_list.extend(new_list)
        return sensor_list

    @staticmethod
    def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        """Migrate config entry."""
        # v1 stored sensor indexes in config_entry.options[CONF_SENSOR_INDICES] as list[int]
        # v2 stores sensor indexes in config_entry.options[CONF_SENSOR_LIST] as type SensorConfigList = list[dict[str, any]]
        if entry.version == 1:
            CONF_SENSOR_INDICES: Final = "sensor_indices"
            index_list: Any | None = entry.options.get(CONF_SENSOR_INDICES)
            if not index_list or type(index_list) is not list or len(index_list) == 0:
                return True

            sensor_list: SensorConfigList = [
                {CONF_SENSOR_INDEX: int(sensor_index), CONF_SENSOR_READ_KEY: None}
                for sensor_index in index_list
            ]

            new_options = deepcopy(dict(entry.options))
            new_options.pop(CONF_SENSOR_INDICES, None)
            new_options[CONF_SENSOR_LIST] = sensor_list

            new_data = deepcopy(dict(entry.data))

            hass.config_entries.async_update_entry(
                entry, data=new_data, options=new_options, version=SCHEMA_VERSION
            )

        return True
