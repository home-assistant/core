"""Config flow for WattTime integration."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aiowatttime import Client
from aiowatttime.errors import CoordinatesNotFoundError, InvalidCredentialsError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_BALANCING_AUTHORITY_ABBREV, DOMAIN, LOGGER

CONF_LOCATION_TYPE = "location_type"

LOCATION_TYPE_COORDINATES = "Specify coordinates"
LOCATION_TYPE_HOME = "Use home location"

STEP_COORDINATES_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LATITUDE): cv.latitude,
        vol.Required(CONF_LONGITUDE): cv.longitude,
    }
)

STEP_LOCATION_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LOCATION_TYPE): vol.In(
            [LOCATION_TYPE_HOME, LOCATION_TYPE_COORDINATES]
        ),
    }
)

STEP_REAUTH_CONFIRM_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WattTime."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._client: Client | None = None
        self._data: dict[str, Any] = {}

    async def _async_validate_credentials(
        self, username: str, password: str, error_step_id: str, error_schema: vol.Schema
    ):
        """Validate input credentials and proceed accordingly."""
        session = aiohttp_client.async_get_clientsession(self.hass)

        try:
            self._client = await Client.async_login(username, password, session=session)
        except InvalidCredentialsError:
            return self.async_show_form(
                step_id=error_step_id,
                data_schema=error_schema,
                errors={"base": "invalid_auth"},
                description_placeholders={CONF_USERNAME: username},
            )
        except Exception as err:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception while logging in: %s", err)
            return self.async_show_form(
                step_id=error_step_id,
                data_schema=error_schema,
                errors={"base": "unknown"},
                description_placeholders={CONF_USERNAME: username},
            )

        # If an entry already exists, we're in a re-auth flow – store the new data and
        # reload the config entry:
        if existing_entry := await self.async_set_unique_id(
            f"{self._data[CONF_LATITUDE]}, {self._data[CONF_LONGITUDE]}"
        ):
            self.hass.config_entries.async_update_entry(existing_entry, data=self._data)
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(existing_entry.entry_id)
            )
            return self.async_abort(reason="reauth_successful")

        # ...otherwise, we're setting up a new config entry:
        self._data[CONF_USERNAME] = username
        self._data[CONF_PASSWORD] = password
        return await self.async_step_location()

    async def async_step_coordinates(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the coordinates step."""
        if not user_input:
            return self.async_show_form(
                step_id="coordinates", data_schema=STEP_COORDINATES_DATA_SCHEMA
            )

        if TYPE_CHECKING:
            assert self._client

        unique_id = f"{user_input[CONF_LATITUDE]}, {user_input[CONF_LONGITUDE]}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        try:
            grid_region = await self._client.emissions.async_get_grid_region(
                user_input[CONF_LATITUDE], user_input[CONF_LONGITUDE]
            )
        except CoordinatesNotFoundError:
            return self.async_show_form(
                step_id="coordinates",
                data_schema=STEP_COORDINATES_DATA_SCHEMA,
                errors={CONF_LATITUDE: "unknown_coordinates"},
            )
        except Exception as err:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception while getting region: %s", err)
            return self.async_show_form(
                step_id="coordinates",
                data_schema=STEP_COORDINATES_DATA_SCHEMA,
                errors={"base": "unknown"},
            )

        return self.async_create_entry(
            title=unique_id,
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_LATITUDE: user_input[CONF_LATITUDE],
                CONF_LONGITUDE: user_input[CONF_LONGITUDE],
                CONF_BALANCING_AUTHORITY_ABBREV: grid_region["abbrev"],
            },
        )

    async def async_step_location(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the "pick a location" step."""
        if not user_input:
            return self.async_show_form(
                step_id="location", data_schema=STEP_LOCATION_DATA_SCHEMA
            )

        if user_input[CONF_LOCATION_TYPE] == LOCATION_TYPE_COORDINATES:
            return self.async_show_form(
                step_id="coordinates", data_schema=STEP_COORDINATES_DATA_SCHEMA
            )
        return await self.async_step_coordinates(
            {
                CONF_LATITUDE: self.hass.config.latitude,
                CONF_LONGITUDE: self.hass.config.longitude,
            }
        )

    async def async_step_reauth(self, config: ConfigType) -> FlowResult:
        """Handle configuration by re-auth."""
        self._data = {**config}
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-auth completion."""
        if not user_input:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=STEP_REAUTH_CONFIRM_DATA_SCHEMA,
                description_placeholders={CONF_USERNAME: self._data[CONF_USERNAME]},
            )

        self._data[CONF_PASSWORD] = user_input[CONF_PASSWORD]

        return await self._async_validate_credentials(
            self._data[CONF_USERNAME],
            self._data[CONF_PASSWORD],
            "reauth_confirm",
            STEP_REAUTH_CONFIRM_DATA_SCHEMA,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if not user_input:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        return await self._async_validate_credentials(
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
            "user",
            STEP_USER_DATA_SCHEMA,
        )
