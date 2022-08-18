"""Config flow for Aqara."""
from __future__ import annotations

import logging
from typing import Any

from aqara_iot import AqaraOpenAPI
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import AQARA_COUNTRIES, CONF_COUNTRY_CODE, DOMAIN

_LOGGER = logging.getLogger(__name__)

REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class AqaraConfigFlow(ConfigFlow, domain=DOMAIN):
    """Aqara Config Flow."""

    entry: ConfigEntry | None = None

    @staticmethod
    def _try_login(user_input: dict[str, Any]) -> bool:
        """Try login."""

        response = False

        api = AqaraOpenAPI(user_input[CONF_COUNTRY_CODE])

        response = api.get_auth(
            username=user_input[CONF_USERNAME],
            password=user_input[CONF_PASSWORD],
            schema="",
        )
        if response is False:
            _LOGGER.debug("get_auth fail")
            return False

        return True

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Step user."""
        errors = {}

        if user_input is not None:
            response = await self.hass.async_add_executor_job(
                self._try_login, user_input
            )

            if response is True:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input,
                )

            errors["base"] = "login_error"

        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_COUNTRY_CODE,
                        default=user_input.get(CONF_COUNTRY_CODE, "China"),
                    ): vol.In(
                        # We don't pass a dict {code:name} because country codes can be duplicate.
                        [country.country_code for country in AQARA_COUNTRIES]
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
        )
