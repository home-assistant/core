#!/usr/bin/env python3
"""Config flow for Tuya."""

import logging

from tuya_iot import ProjectType, TuyaOpenAPI
import voluptuous as vol

from homeassistant import config_entries

from .const import (
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_APP_TYPE,
    CONF_COUNTRY_CODE,
    CONF_ENDPOINT,
    CONF_PASSWORD,
    CONF_PROJECT_TYPE,
    CONF_USERNAME,
    DOMAIN,
    TUYA_APP_TYPE,
    TUYA_ENDPOINT,
    TUYA_PROJECT_TYPE,
)

RESULT_SINGLE_INSTANCE = "single_instance_allowed"
RESULT_AUTH_FAILED = "invalid_auth"
TUYA_ENDPOINT_BASE = "https://openapi.tuyacn.com"

_LOGGER = logging.getLogger(__name__)

# Project Type
DATA_SCHEMA_PROJECT_TYPE = vol.Schema(
    {vol.Required(CONF_PROJECT_TYPE, default=0): vol.In(TUYA_PROJECT_TYPE)}
)

# INDUSTY_SOLUTIONS Schema
DATA_SCHEMA_INDUSTRY_SOLUTIONS = vol.Schema(
    {
        vol.Required(CONF_ENDPOINT): vol.In(TUYA_ENDPOINT),
        vol.Required(CONF_ACCESS_ID): str,
        vol.Required(CONF_ACCESS_SECRET): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

# SMART_HOME Schema
DATA_SCHEMA_SMART_HOME = vol.Schema(
    {
        vol.Required(CONF_ACCESS_ID): str,
        vol.Required(CONF_ACCESS_SECRET): str,
        vol.Required(CONF_APP_TYPE): vol.In(TUYA_APP_TYPE),
        vol.Required(CONF_COUNTRY_CODE): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class TuyaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Tuya Config Flow."""

    def __init__(self) -> None:
        """Init tuya config flow."""
        super().__init__()
        self.conf_project_type = None

    @staticmethod
    def _try_login(user_input):
        project_type = ProjectType(user_input[CONF_PROJECT_TYPE])
        api = TuyaOpenAPI(
            user_input[CONF_ENDPOINT]
            if project_type == ProjectType.INDUSTY_SOLUTIONS
            else "",
            user_input[CONF_ACCESS_ID],
            user_input[CONF_ACCESS_SECRET],
            project_type,
        )
        api.set_dev_channel("hass")

        if project_type == ProjectType.INDUSTY_SOLUTIONS:
            response = api.login(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
        else:
            api.endpoint = TUYA_ENDPOINT_BASE
            response = api.login(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                user_input[CONF_COUNTRY_CODE],
                user_input[CONF_APP_TYPE],
            )
            if response.get("success", False) and isinstance(
                api.token_info.platform_url, str
            ):
                api.endpoint = api.token_info.platform_url
                user_input[CONF_ENDPOINT] = api.token_info.platform_url

        _LOGGER.debug("TuyaConfigFlow._try_login finish, response:, %s", response)
        return response

    async def async_step_user(self, user_input=None):
        """Step user."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA_PROJECT_TYPE
            )

        self.conf_project_type = user_input[CONF_PROJECT_TYPE]

        return await self.async_step_login()

    async def async_step_login(self, user_input=None):
        """Step login."""
        errors = {}
        if user_input is not None:
            assert self.conf_project_type is not None
            user_input[CONF_PROJECT_TYPE] = self.conf_project_type

            response = await self.hass.async_add_executor_job(
                self._try_login, user_input
            )

            if response.get("success", False):
                _LOGGER.debug("TuyaConfigFlow.async_step_user login success")
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input,
                )
            errors["base"] = RESULT_AUTH_FAILED

        if ProjectType(self.conf_project_type) == ProjectType.SMART_HOME:
            return self.async_show_form(
                step_id="login", data_schema=DATA_SCHEMA_SMART_HOME, errors=errors
            )

        return self.async_show_form(
            step_id="login",
            data_schema=DATA_SCHEMA_INDUSTRY_SOLUTIONS,
            errors=errors,
        )
