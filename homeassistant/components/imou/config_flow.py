"""Config flow for Imou."""

from __future__ import annotations

import logging
from typing import Any

from pyimouapi.exceptions import (
    ConnectFailedException,
    ImouException,
    InvalidAppIdOrSecretException,
    RequestFailedException,
)
from pyimouapi.openapi import ImouOpenApiClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import API_URLS, CONF_API_URL, CONF_APP_ID, CONF_APP_SECRET, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _imou_exception_to_config_error(exception: ImouException) -> str:
    """Map library exceptions to stable Home Assistant config-flow error keys."""
    if isinstance(exception, InvalidAppIdOrSecretException):
        return "invalid_auth"
    if isinstance(exception, ConnectFailedException | RequestFailedException):
        return "cannot_connect"
    _LOGGER.debug("Imou error during config flow: %s", exception.message)
    return "unknown"


class ImouConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Imou integration."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the config flow."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_APP_ID])
            self._abort_if_unique_id_configured()
            api_client = ImouOpenApiClient(
                user_input[CONF_APP_ID],
                user_input[CONF_APP_SECRET],
                API_URLS[user_input[CONF_API_URL]],
            )
            try:
                await api_client.async_get_token()
            except ImouException as exception:
                errors["base"] = _imou_exception_to_config_error(exception)
            else:
                return self.async_create_entry(
                    title=DOMAIN,
                    data={
                        CONF_APP_ID: user_input[CONF_APP_ID],
                        CONF_APP_SECRET: user_input[CONF_APP_SECRET],
                        CONF_API_URL: user_input[CONF_API_URL],
                    },
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_APP_ID): str,
                    vol.Required(CONF_APP_SECRET): str,
                    vol.Required(CONF_API_URL, default="sg"): SelectSelector(
                        SelectSelectorConfig(
                            options=list(API_URLS),
                            translation_key="api_url",
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            errors=errors,
        )
