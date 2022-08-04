"""Config flow for Aqara."""
from __future__ import annotations

import logging
from typing import Any

from aqara_iot import AqaraOpenAPI
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.exceptions import (
    HomeAssistantError,
)

from .const import (
    CONF_COUNTRY_CODE,
    CONF_ENDPOINT,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
    AQARA_COUNTRIES,
    AQARA_RESPONSE_CODE,
    AQARA_RESPONSE_MSG,
)

_LOGGER = logging.getLogger(__name__)


class AqaraConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Aqara Config Flow."""

    @staticmethod
    def _try_login(user_input: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        """Try login."""
        response = {}

        country = [
            country
            for country in AQARA_COUNTRIES
            if country.name == user_input[CONF_COUNTRY_CODE]
        ][0]

        data = {
            CONF_ENDPOINT: country.endpoint,
            CONF_USERNAME: user_input[CONF_USERNAME],
            CONF_PASSWORD: user_input[CONF_PASSWORD],
            CONF_COUNTRY_CODE: country.country_code,
        }

        api = AqaraOpenAPI(country.country_code)

        response = api.get_auth(
            username=data[CONF_USERNAME],
            password=data[CONF_PASSWORD],
            schema="",
        )
        if response is False:
            _LOGGER.debug("get_auth fail")
            return False, data

        return True, data

    async def async_step_user(self, user_input=None):
        """Step user."""
        errors = {}
        placeholders = {}

        if user_input is not None:
            response, data = await self.hass.async_add_executor_job(
                self._try_login, user_input
            )

            if response is True:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=data,
                )
            else:
                errors["base"] = "login_error"
                placeholders = {
                    AQARA_RESPONSE_CODE: -1,
                    AQARA_RESPONSE_MSG: "error",
                }

        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_COUNTRY_CODE,
                        default=user_input.get(
                            CONF_COUNTRY_CODE, "China"
                        ),  # United States
                    ): vol.In(
                        # We don't pass a dict {code:name} because country codes can be duplicate.
                        [country.name for country in AQARA_COUNTRIES]
                    ),
                    vol.Required(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                    ): str,
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
