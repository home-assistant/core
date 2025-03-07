"""Configuration validation for PurpleAir integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final

from aiopurpleair.endpoints.sensors import NearbySensorResult
from aiopurpleair.errors import InvalidApiKeyError, PurpleAirError

from homeassistant.core import HomeAssistant

from .const import LOGGER, SENSOR_FIELDS_TO_RETRIEVE
from .coordinator import GetSensorsResponse, async_get_api

CONF_UNKNOWN: Final = "unknown"
CONF_BASE: Final = "base"
CONF_INVALID_API_KEY: Final = "invalid_api_key"
CONF_NO_SENSORS_FOUND: Final = "no_sensors_found"
CONF_NO_SENSOR_FOUND: Final = "no_sensor_found"

LIMIT_RESULTS: Final = 25


@dataclass
class ConfigValidation:
    """Configuration validation."""

    data: Any = None
    errors: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    async def async_validate_api_key(
        hass: HomeAssistant, api_key: str
    ) -> ConfigValidation:
        """Validate API key."""
        api = async_get_api(hass, api_key)
        errors = {}

        try:
            await api.async_check_api_key()
        except InvalidApiKeyError:
            errors[CONF_BASE] = CONF_INVALID_API_KEY
        except PurpleAirError as err:
            LOGGER.error("PurpleAir error while checking API key: %s", err)
            errors[CONF_BASE] = CONF_UNKNOWN
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("Unexpected exception while checking API key: %s", err)
            errors[CONF_BASE] = CONF_UNKNOWN

        if errors:
            return ConfigValidation(errors=errors)

        return ConfigValidation(data=None)

    @staticmethod
    async def async_validate_coordinates(
        hass: HomeAssistant,
        api_key: str,
        latitude: float,
        longitude: float,
        distance: float,
    ) -> ConfigValidation:
        """Validate coordinates."""
        api = async_get_api(hass, api_key)
        errors = {}

        try:
            nearby_sensor_list: list[
                NearbySensorResult
            ] = await api.sensors.async_get_nearby_sensors(
                SENSOR_FIELDS_TO_RETRIEVE,
                latitude,
                longitude,
                distance,
                limit_results=LIMIT_RESULTS,
            )
        except PurpleAirError as err:
            LOGGER.error("PurpleAir error while getting nearby sensors: %s", err)
            errors[CONF_BASE] = CONF_UNKNOWN
        except Exception as err:  # noqa: BLE001
            LOGGER.exception(
                "Unexpected exception while getting nearby sensors: %s", err
            )
            errors[CONF_BASE] = CONF_UNKNOWN
        else:
            if not nearby_sensor_list or len(nearby_sensor_list) == 0:
                errors[CONF_BASE] = CONF_NO_SENSORS_FOUND

        if errors:
            return ConfigValidation(errors=errors)

        return ConfigValidation(data=nearby_sensor_list)

    @staticmethod
    async def async_validate_sensor(
        hass: HomeAssistant, api_key: str, sensor_index: int, read_key: str | None
    ) -> ConfigValidation:
        """Validate sensor."""
        api = async_get_api(hass, api_key)
        errors = {}

        index_list: list[int] = [sensor_index]
        read_key_list: list[str] | None = None
        if type(read_key) is str:
            read_key_list = [read_key]

        try:
            sensors_response: GetSensorsResponse = await api.sensors.async_get_sensors(
                SENSOR_FIELDS_TO_RETRIEVE,
                sensor_indices=index_list,
                read_keys=read_key_list,
            )
        except PurpleAirError as err:
            LOGGER.error("PurpleAir error while getting sensor data: %s", err)
            errors[CONF_BASE] = CONF_UNKNOWN
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("Unexpected exception while getting sensor data: %s", err)
            errors[CONF_BASE] = CONF_UNKNOWN
        else:
            if (
                not sensors_response
                or not sensors_response.data
                or sensors_response.data.get(sensor_index) is None
            ):
                errors[CONF_BASE] = CONF_NO_SENSOR_FOUND

        if errors:
            return ConfigValidation(errors=errors)

        return ConfigValidation(data=sensors_response)
