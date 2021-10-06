"""Config flow for Tuya."""
from __future__ import annotations

import logging
from typing import Any

from tuya_iot import AuthType, TuyaOpenAPI
import voluptuous as vol

from homeassistant import config_entries

from .const import (
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_APP_TYPE,
    CONF_AUTH_TYPE,
    CONF_COUNTRY_CODE,
    CONF_ENDPOINT,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
    SMARTLIFE_APP,
    TUYA_COUNTRIES,
    TUYA_RESPONSE_CODE,
    TUYA_RESPONSE_MSG,
    TUYA_RESPONSE_PLATFROM_URL,
    TUYA_RESPONSE_RESULT,
    TUYA_RESPONSE_SUCCESS,
    TUYA_SMART_APP,
)

_LOGGER = logging.getLogger(__name__)


class TuyaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Tuya Config Flow."""

    @staticmethod
    def _try_login(user_input: dict[str, Any]) -> tuple[dict[Any, Any], dict[str, Any]]:
        """Try login."""
        response = {}

        country = [
            country
            for country in TUYA_COUNTRIES
            if country.name == user_input[CONF_COUNTRY_CODE]
        ][0]

        data = {
            CONF_ENDPOINT: country.endpoint,
            CONF_AUTH_TYPE: AuthType.CUSTOM,
            CONF_ACCESS_ID: user_input[CONF_ACCESS_ID],
            CONF_ACCESS_SECRET: user_input[CONF_ACCESS_SECRET],
            CONF_USERNAME: user_input[CONF_USERNAME],
            CONF_PASSWORD: user_input[CONF_PASSWORD],
            CONF_COUNTRY_CODE: country.country_code,
        }

        for app_type in ("", TUYA_SMART_APP, SMARTLIFE_APP):
            data[CONF_APP_TYPE] = app_type
            if data[CONF_APP_TYPE] == "":
                data[CONF_AUTH_TYPE] = AuthType.CUSTOM
            else:
                data[CONF_AUTH_TYPE] = AuthType.SMART_HOME

            api = TuyaOpenAPI(
                endpoint=data[CONF_ENDPOINT],
                access_id=data[CONF_ACCESS_ID],
                access_secret=data[CONF_ACCESS_SECRET],
                auth_type=data[CONF_AUTH_TYPE],
            )
            api.set_dev_channel("hass")

            response = api.connect(
                username=data[CONF_USERNAME],
                password=data[CONF_PASSWORD],
                country_code=data[CONF_COUNTRY_CODE],
                schema=data[CONF_APP_TYPE],
            )

            _LOGGER.debug("Response %s", response)

            if response.get(TUYA_RESPONSE_SUCCESS, False):
                break

        return response, data

    async def async_step_user(self, user_input=None):
        """Step user."""
        errors = {}
        placeholders = {}

        if user_input is not None:
            response, data = await self.hass.async_add_executor_job(
                self._try_login, user_input
            )

            if response.get(TUYA_RESPONSE_SUCCESS, False):
                if endpoint := response.get(TUYA_RESPONSE_RESULT, {}).get(
                    TUYA_RESPONSE_PLATFROM_URL
                ):
                    data[CONF_ENDPOINT] = endpoint

                data[CONF_AUTH_TYPE] = data[CONF_AUTH_TYPE].value

                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=data,
                )
            errors["base"] = "login_error"
            placeholders = {
                TUYA_RESPONSE_CODE: response.get(TUYA_RESPONSE_CODE),
                TUYA_RESPONSE_MSG: response.get(TUYA_RESPONSE_MSG),
            }

        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_COUNTRY_CODE,
                        default=user_input.get(CONF_COUNTRY_CODE, "United States"),
                    ): vol.In(
                        # We don't pass a dict {code:name} because country codes can be duplicate.
                        [country.name for country in TUYA_COUNTRIES]
                    ),
                    vol.Required(
                        CONF_ACCESS_ID, default=user_input.get(CONF_ACCESS_ID, "")
                    ): str,
                    vol.Required(
                        CONF_ACCESS_SECRET,
                        default=user_input.get(CONF_ACCESS_SECRET, ""),
                    ): str,
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
