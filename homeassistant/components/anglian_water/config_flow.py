"""Implement a config flow for anglian_water."""

from __future__ import annotations

from pyanglianwater import API
from pyanglianwater.exceptions import (
    InvalidPasswordError,
    InvalidUsernameError,
    ServiceUnavailableError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector

from .const import CONF_DEVICE_ID, DOMAIN, LOGGER


class BlueprintFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Blueprint."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        _errors = {}
        if user_input is not None:
            try:
                if user_input.get(CONF_DEVICE_ID, "") == "":
                    auth = await API.create_via_login(
                        email=user_input[CONF_USERNAME],
                        password=user_input[CONF_PASSWORD],
                    )
                else:
                    auth = await API.create_via_login_existing_device(
                        email=user_input[CONF_USERNAME],
                        password=user_input[CONF_PASSWORD],
                        dev_id=user_input[CONF_DEVICE_ID],
                    )
            except InvalidUsernameError as exception:
                LOGGER.warning(exception)
                _errors["base"] = "auth"
            except InvalidPasswordError as exception:
                LOGGER.warning(exception)
                _errors["base"] = "auth"
            except ServiceUnavailableError:
                LOGGER.warning(
                    "Anglian Water app service is unavailable. Check the app for more information"
                )
                _errors["base"] = "maintenance"
            else:
                user_input[CONF_DEVICE_ID] = auth.device_id
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_DEVICE_ID,
                        default=(user_input or {}).get(CONF_DEVICE_ID, ""),
                    ): selector.TextSelector(),
                    vol.Required(
                        CONF_USERNAME,
                        default=(user_input or {}).get(CONF_USERNAME, ""),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT
                        ),
                    ),
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        ),
                    ),
                }
            ),
            errors=_errors,
        )
