"""Config flow for STIHL iMow integration."""
from __future__ import annotations

import datetime
import logging
from typing import Any

from imow.api import IMowApi
from imow.common.exceptions import LoginError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import (
    API_DEFAULT_LANGUAGE,
    API_UPDATE_INTERVALL_SECONDS,
    CONF_API_TOKEN,
    CONF_API_TOKEN_EXPIRE_TIME,
    CONF_ENTRY_TITLE,
    CONF_MOWER,
    CONF_MOWER_IDENTIFIER,
    CONF_MOWER_MODEL,
    CONF_MOWER_NAME,
    CONF_MOWER_STATE,
    CONF_MOWER_VERSION,
    DOMAIN,
    LANGUAGES,
)

_LOGGER = logging.getLogger(__name__)


# TODO adjust the data schema to the data that you need


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA
    with values provided by the user.
    """
    # TODO validate the data can be used to set up a connection.

    # If your PyPI package is not built with async, pass your methods
    # to the executor:
    session = async_get_clientsession(hass)

    imow = IMowApi(
        email=data["email"],
        password=data["password"],
        aiohttp_session=session,
    )
    try:
        token, expire_time = await imow.get_token(
            force_reauth=True, return_expire_time=True
        )
    except LoginError as e:
        await imow.close()
        _LOGGER.exception(e)
        raise InvalidAuth

    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth

    # Return info that you want to store in the config entry.
    mowers = []
    for mower in await imow.receive_mowers():
        mowers_state = dict(mower.__dict__)
        del mowers_state["imow"]
        mowers.append(
            {
                CONF_MOWER_NAME: mower.name,
                CONF_MOWER_IDENTIFIER: mower.id,
                CONF_MOWER_MODEL: mower.deviceTypeDescription,
                CONF_MOWER_VERSION: mower.softwarePacket,
                CONF_MOWER_STATE: mowers_state,
            }
        )
    await imow.close()
    return {
        CONF_API_TOKEN: token,
        CONF_API_TOKEN_EXPIRE_TIME: datetime.datetime.timestamp(expire_time),
        "user_input": data,
        CONF_MOWER: mowers,
    }


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("email"): cv.string,
        vol.Required("password"): cv.string,
    },
)
STEP_ADVANCED = vol.Schema(
    {
        vol.Optional("language", default=API_DEFAULT_LANGUAGE): vol.In(
            [e.value for e in LANGUAGES]
        ),
        vol.Optional("polling_interval", default=API_UPDATE_INTERVALL_SECONDS): vol.In(
            [30, 60, 120, 300]
        ),
    }
)


class StihlImowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for STIHL iMow."""

    VERSION = 1

    def __init__(self):
        """Initialize config flow."""
        self.data = {}
        self.available_mowers = []
        self.token = None
        self.token_expire = None
        self.language = None
        self.polling_interval = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                last_step=False,
            )

        errors = {}

        try:
            self.data = await validate_input(self.hass, user_input)
            self.available_mowers = self.data[CONF_MOWER]
            self.token = self.data[CONF_API_TOKEN]
            self.token_expire = self.data[CONF_API_TOKEN_EXPIRE_TIME]

        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:

            return await self.async_step_advanced()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            last_step=False,
        )

    async def async_step_advanced(
        self, user_input: dict[str, int] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="advanced", data_schema=STEP_ADVANCED)

        errors = {}

        try:
            self.language = LANGUAGES(user_input["language"]).name
            self.polling_interval = user_input["polling_interval"]

        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            self.data["language"] = self.language
            self.data["polling_interval"] = self.polling_interval
            return self.async_create_entry(title=CONF_ENTRY_TITLE, data=self.data)

        return self.async_show_form(
            step_id="advanced",
            data_schema=STEP_ADVANCED,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
