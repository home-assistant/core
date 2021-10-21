"""Config flow for Rointe Heaters integration."""
from __future__ import annotations

from typing import Any

from rointesdk.rointe_api import RointeAPI
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import CONF_INSTALLATION, CONF_PASSWORD, CONF_USERNAME, DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Rointe Heaters."""

    VERSION = 1

    def __init__(self) -> None:
        """Config flow init."""
        self.step_user_data: dict[str, Any] | None = None
        self.step_user_local_id: str | None = None
        self.step_user_installations: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step: User credentials validation."""

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        rointe_api = RointeAPI(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])

        login_error_code = await self.hass.async_add_executor_job(
            rointe_api.initialize_authentication
        )

        if not login_error_code.success or not rointe_api.is_logged_in():
            LOGGER.error(
                "Error during authentication: %s", login_error_code.error_message
            )
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors={"base": "invalid_auth"},
            )

        installations_response = await self.hass.async_add_executor_job(
            rointe_api.get_installations
        )

        if not installations_response.success:
            LOGGER.error(
                "Error retrieving installations: %s",
                installations_response.error_message,
            )

            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors={"base": "unable_get_installations"},
            )

        installations = installations_response.data

        # If we get this far then we have logged in and determined the local_id. Go the next step.
        self.step_user_data = user_input
        self.step_user_installations = installations

        return await self.async_step_installation(None)

    async def async_step_installation(
        self, user_input: dict[str, Any] | None
    ) -> FlowResult:
        """Select the installation."""
        if not user_input or CONF_INSTALLATION not in user_input:
            return self.async_show_form(
                step_id="installation",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_INSTALLATION): vol.In(
                            self.step_user_installations
                        )
                    }
                ),
            )

        assert self.step_user_data is not None
        assert self.step_user_installations is not None

        # check if this installation has already been added.
        await self.async_set_unique_id(user_input[CONF_INSTALLATION])
        self._abort_if_unique_id_configured()

        user_data = {
            CONF_INSTALLATION: user_input[CONF_INSTALLATION],
            CONF_USERNAME: self.step_user_data[CONF_USERNAME],
            CONF_PASSWORD: self.step_user_data[CONF_PASSWORD],
        }

        LOGGER.debug(
            "Config flow completed for zone [%s]", user_data[CONF_INSTALLATION]
        )

        return self.async_create_entry(
            title=self.step_user_installations[user_input[CONF_INSTALLATION]],
            description="Rointe",
            data=user_data,
        )
