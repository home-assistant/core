"""Config flow for Tuya."""
from __future__ import annotations

import logging
from typing import Any

from tuya_iot import ProjectType, TuyaOpenAPI
import voluptuous as vol
from voluptuous.schema_builder import UNDEFINED

from homeassistant import config_entries

from .const import (
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_APP_TYPE,
    CONF_COUNTRY_CODE,
    CONF_ENDPOINT,
    CONF_PASSWORD,
    CONF_PROJECT_TYPE,
    CONF_REGION,
    CONF_USERNAME,
    DOMAIN,
    SMARTLIFE_APP,
    TUYA_REGIONS,
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

        data = {
            CONF_ENDPOINT: TUYA_REGIONS[user_input[CONF_REGION]],
            CONF_PROJECT_TYPE: ProjectType.INDUSTY_SOLUTIONS,
            CONF_ACCESS_ID: user_input[CONF_ACCESS_ID],
            CONF_ACCESS_SECRET: user_input[CONF_ACCESS_SECRET],
            CONF_USERNAME: user_input[CONF_USERNAME],
            CONF_PASSWORD: user_input[CONF_PASSWORD],
            CONF_COUNTRY_CODE: user_input[CONF_REGION],
        }

        for app_type in ("", TUYA_SMART_APP, SMARTLIFE_APP):
            data[CONF_APP_TYPE] = app_type
            if data[CONF_APP_TYPE] == "":
                data[CONF_PROJECT_TYPE] = ProjectType.INDUSTY_SOLUTIONS
            else:
                data[CONF_PROJECT_TYPE] = ProjectType.SMART_HOME

            api = TuyaOpenAPI(
                endpoint=data[CONF_ENDPOINT],
                access_id=data[CONF_ACCESS_ID],
                access_secret=data[CONF_ACCESS_SECRET],
                project_type=data[CONF_PROJECT_TYPE],
            )
            api.set_dev_channel("hass")

            response = api.login(
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

                data[CONF_PROJECT_TYPE] = data[CONF_PROJECT_TYPE].value

                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=data,
                )
            errors["base"] = "login_error"
            placeholders = {
                TUYA_RESPONSE_CODE: response.get(TUYA_RESPONSE_CODE),
                TUYA_RESPONSE_MSG: response.get(TUYA_RESPONSE_MSG),
            }

        def _schema_default(key: str) -> str | UNDEFINED:
            if not user_input:
                return UNDEFINED
            return user_input[key]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_REGION, default=_schema_default(CONF_REGION)
                    ): vol.In(TUYA_REGIONS.keys()),
                    vol.Required(
                        CONF_ACCESS_ID, default=_schema_default(CONF_ACCESS_ID)
                    ): str,
                    vol.Required(
                        CONF_ACCESS_SECRET, default=_schema_default(CONF_ACCESS_SECRET)
                    ): str,
                    vol.Required(
                        CONF_USERNAME, default=_schema_default(CONF_USERNAME)
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=_schema_default(CONF_PASSWORD)
                    ): str,
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )
