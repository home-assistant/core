"""Config flow for WattTime integration."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from aiowatttime import Client
from aiowatttime.errors import (
    CoordinatesNotFoundError,
    InvalidCredentialsError,
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
        if not user_input:
            return self.async_show_form(
                step_id="coordinates", data_schema=self.coordinates_schema
            )

        if TYPE_CHECKING:
            assert self._client

        unique_id = f"{user_input[CONF_LATITUDE]}, {user_input[CONF_LONGITUDE]}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        try:
            await self._client.emissions.async_get_grid_region(
                user_input[CONF_LATITUDE], user_input[CONF_LONGITUDE]
            )
        except CoordinatesNotFoundError:
            return self.async_show_form(
                step_id="coordinates",
                data_schema=self.coordinates_schema,
                errors={CONF_LATITUDE: "unknown_coordinates"},
            )

        except Exception as err:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception while getting region: %s", err)
            return self.async_show_form(
                step_id="coordinates",
                data_schema=self.coordinates_schema,
                errors={"base": "unknown"},
            )

        return self.async_create_entry(
            title=unique_id,
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_LATITUDE: user_input[CONF_LATITUDE],
                CONF_LONGITUDE: user_input[CONF_LONGITUDE],
            },
        )

    async def async_step_login(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the login step."""
        if not user_input:
            return self.async_show_form(
                step_id="login", data_schema=STEP_LOGIN_DATA_SCHEMA
            )

        # If this is the first time we've seen these credentials, check that they're
        # valid – this allows a user to configure multiple config entries without
        # rechecking the credentials each time:
        valid_creds = self.hass.data.setdefault(f"{DOMAIN}_checked_creds", set())
        valid_creds_lock = self.hass.data.setdefault(
            f"{DOMAIN}_checked_creds_lock", asyncio.Lock()
        )

        session = aiohttp_client.async_get_clientsession(self.hass)

        async with valid_creds_lock:
            if user_input[CONF_USERNAME] not in valid_creds:
                try:
                    self._client = await Client.async_login(
                        user_input[CONF_USERNAME],
                        user_input[CONF_PASSWORD],
                        session=session,
                    )
                except InvalidCredentialsError:
                    return self.async_show_form(
                        step_id="login",
                        data_schema=STEP_LOGIN_DATA_SCHEMA,
                        errors={CONF_USERNAME: "invalid_auth"},
                    )
                except Exception as err:  # pylint: disable=broad-except
                    LOGGER.exception("Unexpected exception while logging in: %s", err)
                    return self.async_show_form(
                        step_id="login",
                        data_schema=STEP_LOGIN_DATA_SCHEMA,
                        errors={"base": "unknown"},
                    )
                else:
                    valid_creds.add(user_input[CONF_USERNAME])

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]
        return await self.async_step_coordinates()

    async def async_step_register(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user registration step."""
        if not user_input:
            return self.async_show_form(
                step_id="register", data_schema=STEP_REGISTER_DATA_SCHEMA
            )

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
            return self.async_show_form(
                step_id="register",
                data_schema=STEP_REGISTER_DATA_SCHEMA,
                errors={CONF_USERNAME: "username_taken"},
            )
        except Exception as err:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception while registering: %s", err)
            return self.async_show_form(
                step_id="register",
                data_schema=STEP_REGISTER_DATA_SCHEMA,
                errors={"base": "unknown"},
            )

        return await self.async_step_login(
            {
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if not user_input:
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
