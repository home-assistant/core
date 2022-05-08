"""Config flow for ezviz."""
from __future__ import annotations

import logging
from typing import Any

from pyhyypapi.client import HyypClient
from pyhyypapi.constants import DEFAULT_TIMEOUT
from pyhyypapi.exceptions import HTTPError, HyypApiError, InvalidURL
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TIMEOUT, CONF_TOKEN
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    ATTR_ARM_CODE,
    ATTR_BYPASS_CODE,
    CONF_PKG,
    DOMAIN,
    PKG_ADT_SECURE_HOME,
    PKG_IDS_HYYP,
)

_LOGGER = logging.getLogger(__name__)
DEFAULT_OPTIONS = {
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
}


def _validate_and_create_auth(data: dict) -> dict[str, Any]:
    """Try to login to IDS Hyyp account and return token."""
    # Verify cloud credentials by attempting a login request with username and password.
    # Return login token.

    hyyp_client = HyypClient(
        data[CONF_EMAIL],
        data[CONF_PASSWORD],
        data[CONF_PKG],
    )

    hyyp_token = hyyp_client.login()

    return {CONF_TOKEN: hyyp_token[CONF_TOKEN], CONF_PKG: data[CONF_PKG]}


class HyypConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hyyp."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> HyypOptionsFlowHandler:
        """Get the options flow for this handler."""
        return HyypOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""

        errors = {}
        token_data = {}

        if user_input is not None:

            await self.async_set_unique_id(user_input[CONF_EMAIL])
            self._abort_if_unique_id_configured()

            try:
                token_data = await self.hass.async_add_executor_job(
                    _validate_and_create_auth, user_input
                )

            except InvalidURL:
                errors["base"] = "invalid_host"

            except HTTPError:
                errors["base"] = "cannot_connect"

            except HyypApiError:
                errors["base"] = "invalid_auth"

            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                return self.async_abort(reason="unknown")

            else:
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data=token_data,
                    options=DEFAULT_OPTIONS,
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_PKG, default=PKG_ADT_SECURE_HOME): vol.In(
                    [PKG_ADT_SECURE_HOME, PKG_IDS_HYYP]
                ),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )


class HyypOptionsFlowHandler(OptionsFlow):
    """Handle Hyyp client options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Hyyp options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = vol.Schema(
            {
                vol.Optional(
                    CONF_TIMEOUT,
                    default=self.config_entry.options.get(
                        CONF_TIMEOUT, DEFAULT_TIMEOUT
                    ),
                ): int,
                vol.Optional(ATTR_ARM_CODE): str,
                vol.Optional(ATTR_BYPASS_CODE): str,
            }
        )

        return self.async_show_form(step_id="init", data_schema=options)
