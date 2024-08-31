"""Config flow for Spider."""

import logging
from typing import Any

from spiderpy.spiderapi import SpiderApi, SpiderApiException, UnauthorizedException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA_USER = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)

RESULT_AUTH_FAILED = "auth_failed"
RESULT_CONN_ERROR = "conn_error"
RESULT_SUCCESS = "success"


class SpiderConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Spider config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the Spider flow."""
        self.data = {
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        }

    def _try_connect(self):
        """Try to connect and check auth."""
        try:
            SpiderApi(
                self.data[CONF_USERNAME],
                self.data[CONF_PASSWORD],
                self.data[CONF_SCAN_INTERVAL],
            )
        except SpiderApiException:
            return RESULT_CONN_ERROR
        except UnauthorizedException:
            return RESULT_AUTH_FAILED

        return RESULT_SUCCESS

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}
        if user_input is not None:
            self.data[CONF_USERNAME] = user_input["username"]
            self.data[CONF_PASSWORD] = user_input["password"]

            result = await self.hass.async_add_executor_job(self._try_connect)

            if result == RESULT_SUCCESS:
                return self.async_create_entry(
                    title=DOMAIN,
                    data=self.data,
                )
            if result != RESULT_AUTH_FAILED:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
                return self.async_abort(reason=result)

            errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA_USER,
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import spider config from configuration.yaml."""
        return await self.async_step_user(import_data)
