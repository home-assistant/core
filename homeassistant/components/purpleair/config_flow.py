"""Config flow for PurpleAir integration."""
from __future__ import annotations

from typing import Any, cast

from aiopurpleair import API
from aiopurpleair.errors import InvalidApiKeyError, PurpleAirError
from aiopurpleair.models.sensors import SensorModel
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client, config_validation as cv

from .const import CONF_SENSOR_INDEX, DOMAIN, LOGGER

CONF_DISTANCE = "distance"

DEFAULT_DISTANCE = 5

STEP_CHECK_API_KEY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PurpleAir."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._api: API = None  # type: ignore[assignment]
        self._api_key: str = None  # type: ignore[assignment]

    @property
    def step_by_coordinates_schema(self) -> vol.Schema:
        """Define a schema for the by_coordinates step."""
        return vol.Schema(
            {
                vol.Inclusive(
                    CONF_LATITUDE, "coords", default=self.hass.config.latitude
                ): cv.latitude,
                vol.Inclusive(
                    CONF_LONGITUDE, "coords", default=self.hass.config.longitude
                ): cv.longitude,
                vol.Optional(CONF_DISTANCE, default=DEFAULT_DISTANCE): cv.positive_int,
            }
        )

    async def _async_step_create_entry(self, sensor: SensorModel) -> FlowResult:
        """Create the config entry."""
        await self.async_set_unique_id(str(sensor.sensor_index))
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=cast(str, sensor.name),
            data={CONF_API_KEY: self._api_key, CONF_SENSOR_INDEX: sensor.sensor_index},
        )

    async def async_step_check_api_key(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="check_api_key", data_schema=STEP_CHECK_API_KEY_SCHEMA
            )

        session = aiohttp_client.async_get_clientsession(self.hass)
        self._api = API(user_input[CONF_API_KEY], session=session)
        errors = {}

        try:
            await self._api.async_check_api_key()
        except InvalidApiKeyError:
            errors[CONF_API_KEY] = "invalid_api_key"
        except PurpleAirError as err:
            LOGGER.error("PurpleAir error while checking API key: %s", err)
            errors["base"] = "unknown"
        except Exception as err:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception while checking API key: %s", err)
            errors["base"] = "unknown"

        if errors:
            return self.async_show_form(
                step_id="check_api_key",
                data_schema=STEP_CHECK_API_KEY_SCHEMA,
                errors=errors,
            )

        self._api_key = user_input[CONF_API_KEY]

        return await self.async_step_by_coordinates()

    async def async_step_by_coordinates(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the selection of a sensor by latitude/longitude."""
        if user_input is None:
            return self.async_show_form(
                step_id="by_coordinates", data_schema=self.step_by_coordinates_schema
            )

        errors = {}

        try:
            [nearest_sensor] = await self._api.sensors.async_get_nearby_sensors(
                ["name"],
                user_input[CONF_LATITUDE],
                user_input[CONF_LONGITUDE],
                user_input[CONF_DISTANCE],
                limit_results=1,
            )
        except ValueError:
            errors["base"] = "no_sensors_near_coordinates"
        except PurpleAirError as err:
            LOGGER.error("PurpleAir error while getting nearby sensors: %s", err)
            errors["base"] = "unknown"
        except Exception as err:  # pylint: disable=broad-except
            LOGGER.exception(
                "Unexpected exception while getting nearby sensors: %s", err
            )
            errors["base"] = "unknown"

        if errors:
            return self.async_show_form(
                step_id="by_coordinates",
                data_schema=self.step_by_coordinates_schema,
                errors=errors,
            )

        return await self._async_step_create_entry(nearest_sensor)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        return await self.async_step_check_api_key()
