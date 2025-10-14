"""Config flow for Hanna Instruments integration."""

from __future__ import annotations

import logging
from typing import Any

from hanna_cloud import AuthenticationError, HannaCloudClient
from requests.exceptions import ConnectionError as RequestsConnectionError, Timeout
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class HannaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hanna Instruments."""

    VERSION = 1
    data_schema = vol.Schema(
        {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
    )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the setup flow."""

        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                client = HannaCloudClient()
                await self.hass.async_add_executor_job(
                    client.authenticate,
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                )
            except (Timeout, RequestsConnectionError):
                errors["base"] = "cannot_connect"
            except AuthenticationError:
                errors["base"] = "invalid_auth"

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.data_schema,
            errors=errors,
        )
