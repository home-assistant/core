"""Config flow for FlexMeasures integration."""
from __future__ import annotations

import logging
from typing import Any

from flexmeasures_client import FlexMeasuresClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .helpers import get_previous_option

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(
            "host", description={"suggested_value": "https://flexmeasures.seita.nl"}
        ): str,
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)


class PlaceholderHub:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self, host: str) -> None:
        """Initialize."""
        self.host = host

    async def authenticate(self, username: str, password: str) -> bool:
        """Test if we can authenticate with the host."""
        return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    # Currently used here solely for config validation (i.e. not returned to be stored in the config entry)
    try:
        client = FlexMeasuresClient(
            host=data["host"],
            email=data["username"],
            password=data["password"],
            ssl=False,
        )
    except Exception as exception:
        raise CannotConnect(exception) from exception
    try:
        await client.get_access_token()
    except Exception as exception:
        raise InvalidAuth(exception) from exception

    # Return info that you want to store in the config entry.
    return {"title": "FlexMeasures"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for FlexMeasures integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        # Support a single FlexMeasures configuration only
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect as exception:
            errors["base"] = "cannot_connect"
            if "host" in str(exception):
                errors["host"] = str(exception)
            elif "email" in str(exception):
                errors["username"] = str(exception)
            elif "password" in str(exception):
                errors["password"] = str(exception)
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        # Show form again, showing captured errors
        # still do invalid_auth validation error is not yet shown properly
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handles options flow for the component."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options for the custom component."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Value of data will be set on the options property of our config_entry instance.
                return self.async_create_entry(title=info["title"], data=user_input)

        options_schema = vol.Schema(
            {
                vol.Required(
                    "host", default=get_previous_option(self.config_entry, "host")
                ): str,
                vol.Required(
                    "username",
                    default=get_previous_option(self.config_entry, "username"),
                ): str,
                vol.Required(
                    "password",
                    default=get_previous_option(self.config_entry, "password"),
                ): str,
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=options_schema, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
