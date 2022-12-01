"""Config flow for PurpleAir integration."""
from __future__ import annotations

from typing import Any

from aiopurpleair import API
from aiopurpleair.errors import InvalidApiKeyError, PurpleAirError
from aiopurpleair.models.sensors import SensorModel
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client, config_validation as cv

from .const import CONF_SENSOR_INDICES, DOMAIN, LOGGER

CONF_DISTANCE = "distance"

DEFAULT_DISTANCE = 5

API_KEY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
    }
)


@callback
def async_get_api(hass: HomeAssistant, api_key: str) -> API:
    """Get an aiopurpleair API object."""
    session = aiohttp_client.async_get_clientsession(hass)
    return API(api_key, session=session)


@callback
def async_get_coordinates_schema(hass: HomeAssistant) -> vol.Schema:
    """Define a schema for the by_coordinates step."""
    return vol.Schema(
        {
            vol.Inclusive(
                CONF_LATITUDE, "coords", default=hass.config.latitude
            ): cv.latitude,
            vol.Inclusive(
                CONF_LONGITUDE, "coords", default=hass.config.longitude
            ): cv.longitude,
            vol.Optional(CONF_DISTANCE, default=DEFAULT_DISTANCE): cv.positive_int,
        }
    )


class FlowError(Exception):
    """Define an exception that indicates a flow error."""


async def async_validate_api_key(hass: HomeAssistant, api_key: str) -> None:
    """Validate an API key."""
    api = async_get_api(hass, api_key)

    try:
        await api.async_check_api_key()
    except InvalidApiKeyError as err:
        raise FlowError("invalid_api_key") from err
    except PurpleAirError as err:
        LOGGER.error("PurpleAir error while checking API key: %s", err)
        raise FlowError("unknown") from err
    except Exception as err:  # pylint: disable=broad-except
        LOGGER.exception("Unexpected exception while checking API key: %s", err)
        raise FlowError("unknown") from err


async def async_validate_coordinates(
    hass: HomeAssistant,
    api_key: str,
    latitude: float,
    longitude: float,
    distance: float,
) -> SensorModel:
    """Validate coordinates."""
    api = async_get_api(hass, api_key)

    try:
        [nearest_sensor] = await api.sensors.async_get_nearby_sensors(
            ["name"], latitude, longitude, distance, limit_results=1
        )
    except ValueError as err:
        raise FlowError("no_sensors_near_coordinates") from err
    except PurpleAirError as err:
        LOGGER.error("PurpleAir error while getting nearby sensors: %s", err)
        raise FlowError("unknown") from err
    except Exception as err:  # pylint: disable=broad-except
        LOGGER.exception("Unexpected exception while getting nearby sensors: %s", err)
        raise FlowError("unknown") from err

    return nearest_sensor


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PurpleAir."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._entry_data: dict[str, Any] = {}

    async def async_step_by_coordinates(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the selection of a sensor by latitude/longitude."""
        if user_input is None:
            return self.async_show_form(
                step_id="by_coordinates",
                data_schema=async_get_coordinates_schema(self.hass),
            )

        api_key = self._entry_data[CONF_API_KEY]

        try:
            nearest_sensor = await async_validate_coordinates(
                self.hass,
                api_key,
                user_input[CONF_LATITUDE],
                user_input[CONF_LONGITUDE],
                user_input[CONF_DISTANCE],
            )
        except FlowError as err:
            return self.async_show_form(
                step_id="by_coordinates",
                data_schema=async_get_coordinates_schema(self.hass),
                errors={"base": str(err)},
            )

        return self.async_create_entry(
            title=api_key[:5],
            data=self._entry_data
            | {CONF_SENSOR_INDICES: [nearest_sensor.sensor_index]},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=API_KEY_SCHEMA)

        api_key = user_input[CONF_API_KEY]

        await self.async_set_unique_id(api_key)
        self._abort_if_unique_id_configured()

        try:
            await async_validate_api_key(self.hass, api_key)
        except FlowError as err:
            return self.async_show_form(
                step_id="user",
                data_schema=API_KEY_SCHEMA,
                errors={"base": str(err)},
            )

        self._entry_data = {CONF_API_KEY: api_key}
        return await self.async_step_by_coordinates()
