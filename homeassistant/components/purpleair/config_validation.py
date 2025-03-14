"""PurpleAir configuration validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final

from aiopurpleair.endpoints.sensors import NearbySensorResult
from aiopurpleair.errors import (
    InvalidApiKeyError,
    InvalidRequestError,
    NotFoundError,
    PurpleAirError,
    RequestError,
)
from aiopurpleair.models.sensors import GetSensorsResponse

from homeassistant.core import HomeAssistant

from .const import LOGGER, SENSOR_FIELDS_TO_RETRIEVE
from .coordinator import async_get_api

LIMIT_RESULTS: Final[int] = 25

CONF_BASE: Final[str] = "base"
CONF_INVALID_API_KEY: Final[str] = "invalid_api_key"
CONF_NO_SENSOR_FOUND: Final[str] = "no_sensor_found"
CONF_NO_SENSORS_FOUND: Final[str] = "no_sensors_found"
CONF_UNKNOWN: Final[str] = "unknown"


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
        except InvalidApiKeyError as err:
            # TODO: Set debug level when debugging in vscode # pylint: disable=fixme
            LOGGER.error(
                "PurpleAir:async_check_api_key():InvalidApiKeyErrorPurpleAir: %s", err
            )
            errors[CONF_BASE] = CONF_INVALID_API_KEY
        except (
            RequestError,
            InvalidRequestError,
            NotFoundError,
            PurpleAirError,
        ) as err:
            LOGGER.error("PurpleAir:async_check_api_key():PurpleAirError : %s", err)
            errors[CONF_BASE] = CONF_UNKNOWN
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("PurpleAir:async_check_api_key():Exception: %s", err)
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
        except InvalidApiKeyError as err:
            LOGGER.error(
                "PurpleAir:async_get_nearby_sensors():InvalidApiKeyError : %s", err
            )
            errors[CONF_BASE] = CONF_INVALID_API_KEY
        except (
            RequestError,
            InvalidRequestError,
            NotFoundError,
            PurpleAirError,
        ) as err:
            LOGGER.error(
                "PurpleAir:async_get_nearby_sensors():PurpleAirError : %s", err
            )
            errors[CONF_BASE] = CONF_UNKNOWN
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("PurpleAir:async_get_nearby_sensors():Exception: %s", err)
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
        except InvalidApiKeyError as err:
            LOGGER.error(
                "PurpleAir:async_get_sensors():InvalidApiKeyErrorPurpleAir: %s", err
            )
            errors[CONF_BASE] = CONF_INVALID_API_KEY
        except (
            RequestError,
            InvalidRequestError,
            NotFoundError,
            PurpleAirError,
        ) as err:
            LOGGER.error("PurpleAir:async_get_sensors():PurpleAirError : %s", err)
            errors[CONF_BASE] = CONF_UNKNOWN
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("PurpleAir:async_get_sensors():Exception: %s", err)
            errors[CONF_BASE] = CONF_UNKNOWN
        else:
            if (
                not sensors_response
                or not sensors_response.data
                or sensors_response.data.get(sensor_index) is None
                or sensors_response.data[sensor_index] is None
                or sensors_response.data[sensor_index].sensor_index != sensor_index
            ):
                errors[CONF_BASE] = CONF_NO_SENSOR_FOUND

        if errors:
            return ConfigValidation(errors=errors)

        return ConfigValidation(data=sensors_response)
