"""Config flow for PurpleAir integration."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from aiopurpleair import API
from aiopurpleair.errors import InvalidApiKeyError, PurpleAirError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_SENSOR_INDICES, DOMAIN, LOGGER

CONF_DISTANCE = "distance"
CONF_NEARBY_SENSOR_OPTIONS = "nearby_sensor_options"
CONF_SENSOR_INDEX = "sensor_index"

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
    """Define a schema for searching for sensors near a coordinate pair."""
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


@callback
def async_get_nearby_sensors_schema(options: list[SelectOptionDict]) -> vol.Schema:
    """Define a schema for selecting a sensor from a list."""
    return vol.Schema(
        {
            vol.Required(CONF_SENSOR_INDEX): SelectSelector(
                SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
            )
        }
    )


@dataclass
class ValidationResult:
    """Define a validation result."""

    data: Any = None
    errors: dict[str, Any] = field(default_factory=dict)


async def async_validate_api_key(hass: HomeAssistant, api_key: str) -> ValidationResult:
    """Validate an API key.

    This method returns a dictionary of errors (if appropriate).
    """
    api = async_get_api(hass, api_key)
    errors = {}

    try:
        await api.async_check_api_key()
    except InvalidApiKeyError:
        errors["base"] = "invalid_api_key"
    except PurpleAirError as err:
        LOGGER.error("PurpleAir error while checking API key: %s", err)
        errors["base"] = "unknown"
    except Exception as err:  # pylint: disable=broad-except
        LOGGER.exception("Unexpected exception while checking API key: %s", err)
        errors["base"] = "unknown"

    if errors:
        return ValidationResult(errors=errors)

    return ValidationResult(data=None)


async def async_validate_coordinates(
    hass: HomeAssistant,
    api_key: str,
    latitude: float,
    longitude: float,
    distance: float,
) -> ValidationResult:
    """Validate coordinates."""
    api = async_get_api(hass, api_key)
    errors = {}

    try:
        nearby_sensor_results = await api.sensors.async_get_nearby_sensors(
            ["name"], latitude, longitude, distance, limit_results=5
        )
    except PurpleAirError as err:
        LOGGER.error("PurpleAir error while getting nearby sensors: %s", err)
        errors["base"] = "unknown"
    except Exception as err:  # pylint: disable=broad-except
        LOGGER.exception("Unexpected exception while getting nearby sensors: %s", err)
        errors["base"] = "unknown"
    else:
        if not nearby_sensor_results:
            errors["base"] = "no_sensors_near_coordinates"

    if errors:
        return ValidationResult(errors=errors)

    return ValidationResult(data=nearby_sensor_results)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PurpleAir."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._flow_data: dict[str, Any] = {}

    async def async_step_by_coordinates(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the discovery of sensors near a latitude/longitude."""
        if user_input is None:
            return self.async_show_form(
                step_id="by_coordinates",
                data_schema=async_get_coordinates_schema(self.hass),
            )

        validation = await async_validate_coordinates(
            self.hass,
            self._flow_data[CONF_API_KEY],
            user_input[CONF_LATITUDE],
            user_input[CONF_LONGITUDE],
            user_input[CONF_DISTANCE],
        )
        if validation.errors:
            return self.async_show_form(
                step_id="by_coordinates",
                data_schema=async_get_coordinates_schema(self.hass),
                errors=validation.errors,
            )

        self._flow_data[CONF_NEARBY_SENSOR_OPTIONS] = [
            SelectOptionDict(
                value=str(result.sensor.sensor_index),
                label=f"{result.sensor.name} ({round(result.distance, 1)} km away)",
            )
            for result in validation.data
        ]

        return await self.async_step_choose_sensor()

    async def async_step_choose_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the selection of a sensor."""
        if user_input is None:
            options = self._flow_data.pop(CONF_NEARBY_SENSOR_OPTIONS)
            return self.async_show_form(
                step_id="choose_sensor",
                data_schema=async_get_nearby_sensors_schema(options),
            )

        return self.async_create_entry(
            title=self._flow_data[CONF_API_KEY][:5],
            data=self._flow_data,
            # Note that we store the sensor indices in options so that later on, we can
            # add/remove additional sensors via an options flow:
            options={CONF_SENSOR_INDICES: [int(user_input[CONF_SENSOR_INDEX])]},
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the re-auth step."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm", data_schema=API_KEY_SCHEMA
            )

        api_key = user_input[CONF_API_KEY]

        validation = await async_validate_api_key(self.hass, api_key)
        if validation.errors:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=API_KEY_SCHEMA,
                errors=validation.errors,
            )

        reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        assert reauth_entry
        self.hass.config_entries.async_update_entry(
            reauth_entry, data={CONF_API_KEY: api_key}
        )
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(reauth_entry.entry_id)
        )
        return self.async_abort(reason="reauth_successful")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=API_KEY_SCHEMA)

        api_key = user_input[CONF_API_KEY]

        self._async_abort_entries_match({CONF_API_KEY: api_key})

        validation = await async_validate_api_key(self.hass, api_key)
        if validation.errors:
            return self.async_show_form(
                step_id="user",
                data_schema=API_KEY_SCHEMA,
                errors=validation.errors,
            )

        self._flow_data = {CONF_API_KEY: api_key}
        return await self.async_step_by_coordinates()
