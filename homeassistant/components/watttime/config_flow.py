"""Config flow for WattTime integration."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aiowatttime import Client
from aiowatttime.errors import (
    CoordinatesNotFoundError,
    InvalidCredentialsError,
    RequestError,
    UsernameTakenError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_EMAIL,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client, config_validation as cv

from .const import AUTH_TYPE_LOGIN, AUTH_TYPE_REGISTER, DOMAIN, LOGGER

CONF_AUTH_TYPE = "auth_type"
CONF_ORGANIZATION = "organization"

STEP_LOGIN_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_REGISTER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_ORGANIZATION): str,
    }
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AUTH_TYPE): vol.In([AUTH_TYPE_LOGIN, AUTH_TYPE_REGISTER]),
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WattTime."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._client: Client | None = None
        self._password: str | None = None
        self._username: str | None = None

    @property
    def coordinates_schema(self) -> vol.Schema:
        """Return the coordinates schema."""
        return vol.Schema(
            {
                vol.Required(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Required(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
            }
        )

    async def async_step_coordinates(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the latitude/longitude step."""
        if user_input is None:
            return self.async_show_form(
                step_id="coordinates", data_schema=self.coordinates_schema
            )

        unique_id = f"{user_input[CONF_LATITUDE]}, {user_input[CONF_LONGITUDE]}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        errors = {}

        if TYPE_CHECKING:
            assert self._client

        try:
            await self._client.emissions.async_get_grid_region(
                user_input[CONF_LATITUDE], user_input[CONF_LONGITUDE]
            )
        except CoordinatesNotFoundError:
            errors["base"] = "unknown_coordinates"
        except RequestError as err:
            LOGGER.exception("Unexpected request error while getting region: %s", err)
            errors["base"] = "unknown"
        except Exception as err:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception while getting region: %s", err)
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(
                title=unique_id,
                data={
                    CONF_USERNAME: self._username,
                    CONF_PASSWORD: self._password,
                    CONF_LATITUDE: user_input[CONF_LATITUDE],
                    CONF_LONGITUDE: user_input[CONF_LONGITUDE],
                },
            )

        return self.async_show_form(
            step_id="coordinates", data_schema=self.coordinates_schema, errors=errors
        )

    async def async_step_login(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the login step."""
        if user_input is None:
            return self.async_show_form(
                step_id="login", data_schema=STEP_LOGIN_DATA_SCHEMA
            )

        errors = {}
        session = aiohttp_client.async_get_clientsession(self.hass)

        try:
            self._client = await Client.async_login(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD], session=session
            )
        except InvalidCredentialsError:
            errors["base"] = "invalid_auth"
        except RequestError as err:
            LOGGER.exception("Unexpected request error while logging in: %s", err)
            errors["base"] = "unknown"
        except Exception as err:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception while logging in: %s", err)
            errors["base"] = "unknown"
        else:
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]
            return await self.async_step_coordinates()

        return self.async_show_form(
            step_id="login", data_schema=STEP_LOGIN_DATA_SCHEMA, errors=errors
        )

    async def async_step_register(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user registration step."""
        if user_input is None:
            return self.async_show_form(
                step_id="register", data_schema=STEP_REGISTER_DATA_SCHEMA
            )

        errors = {}
        session = aiohttp_client.async_get_clientsession(self.hass)

        try:
            await Client.async_register_new_username(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                user_input[CONF_EMAIL],
                user_input[CONF_ORGANIZATION],
                session=session,
            )
        except UsernameTakenError:
            errors["base"] = "username_taken"
        except RequestError as err:
            LOGGER.exception("Unexpected request error while registering: %s", err)
            errors["base"] = "unknown"
        except Exception as err:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception while registering: %s", err)
            errors["base"] = "unknown"
        else:
            return await self.async_step_login(
                {
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                }
            )

        return self.async_show_form(
            step_id="register", data_schema=STEP_REGISTER_DATA_SCHEMA, errors=errors
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        if user_input[CONF_AUTH_TYPE] == AUTH_TYPE_LOGIN:
            return self.async_show_form(
                step_id="login", data_schema=STEP_LOGIN_DATA_SCHEMA
            )
        return self.async_show_form(
            step_id="register", data_schema=STEP_REGISTER_DATA_SCHEMA
        )
