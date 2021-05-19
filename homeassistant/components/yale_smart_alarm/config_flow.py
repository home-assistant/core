"""Adds config flow for Yale Smart Alarm integration."""
from __future__ import annotations

import voluptuous as vol
from yalesmartalarmclient.client import AuthenticationError, YaleSmartAlarmClient

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_CODE, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

from .const import CONF_AREA_ID, DEFAULT_AREA_ID, DEFAULT_NAME, DOMAIN, LOGGER

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_CODE): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_AREA_ID, default=DEFAULT_AREA_ID): cv.string,
    }
)


async def validate_input(hass: core.HomeAssistant, username, password):
    """Validate the user input allows us to connect."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data["username"] == username:
            raise AlreadyConfigured

    try:
        await hass.async_add_executor_job(YaleSmartAlarmClient, username, password)
    except AuthenticationError as e:
        LOGGER.error("Authentication failed. Check credentials %s", e)
        raise InvalidAuth
    except Exception as e:
        LOGGER.error("Connection could not be made %s", e)
        raise CannotConnect

    return True


class YaleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Yale integration."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            code = user_input[CONF_CODE]
            name = user_input.get(CONF_NAME, DEFAULT_NAME)
            area = user_input.get(CONF_AREA_ID, DEFAULT_AREA_ID)

            try:
                await validate_input(self.hass, username, password)
            except AlreadyConfigured:
                return self.async_abort(reason="already_configured")
            except InvalidAuth:
                return self.async_show_form(
                    step_id="user",
                    data_schema=DATA_SCHEMA,
                    errors={"base": "invalid_auth"},
                    description_placeholders={},
                )
            except CannotConnect:
                return self.async_show_form(
                    step_id="user",
                    data_schema=DATA_SCHEMA,
                    errors={"base": "connection_error"},
                    description_placeholders={},
                )

            unique_id = username
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=unique_id,
                data={
                    CONF_USERNAME: username,
                    CONF_PASSWORD: password,
                    CONF_CODE: code,
                    CONF_NAME: name,
                    CONF_AREA_ID: area,
                },
            )
            LOGGER.info("Config entry created successfully")

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class AlreadyConfigured(exceptions.HomeAssistantError):
    """Error to indicate host is already configured."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidInput(exceptions.HomeAssistantError):
    """Error to indicate input data is invalid."""

    def __init__(self, error: str) -> None:
        """Initialize error."""
        super().__init__()
        self.error = error
