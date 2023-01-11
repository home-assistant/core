"""Config flow for smtp integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from smtplib import SMTPAuthenticationError, SMTPException
import socket
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from . import get_smtp_client
from .const import (
    CONF_DEBUG,
    CONF_ENCRYPTION,
    CONF_SERVER,
    DEFAULT_DEBUG,
    DEFAULT_ENCRYPTION,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
    ENCRYPTION_OPTIONS,
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): selector.TextSelector(),
        vol.Optional(CONF_SERVER, default=DEFAULT_HOST): selector.TextSelector(),
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(
            CONF_ENCRYPTION, default=DEFAULT_ENCRYPTION
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(options=ENCRYPTION_OPTIONS)
        ),
        vol.Optional(CONF_USERNAME): selector.TextSelector(),
        vol.Optional(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
        vol.Optional(CONF_DEBUG, default=DEFAULT_DEBUG): selector.BooleanSelector(),
        vol.Optional(CONF_VERIFY_SSL, default=True): selector.BooleanSelector(),
    }
)

_LOGGER = logging.getLogger(__name__)


def validate_input(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate user input."""
    errors: dict[str, str] = {}

    try:
        smtp_client = get_smtp_client(user_input)
        smtp_client.quit()
    except SMTPAuthenticationError as error:
        print(error)
        errors[CONF_USERNAME] = errors[CONF_PASSWORD] = "invalid_auth"
    except (SMTPException, socket.gaierror, ConnectionRefusedError, OSError):
        errors["base"] = "cannot_connect"

    return errors


class SMTPFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for smtp."""

    _reauth_entry: config_entries.ConfigEntry | None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                }
            )
            if not (
                errors := await self.hass.async_add_executor_job(
                    validate_input, user_input
                )
            ):
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_config: dict[str, str]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        _LOGGER.warning(
            "Configuration of the smtp integration in YAML is deprecated and "
            "will be removed in a future release; Your existing configuration "
            "has been imported into the UI automatically and can be safely removed "
            "from your configuration.yaml file"
        )
        return await self.async_step_user(import_config)

    async def async_step_reauth(self, data: Mapping[str, Any]) -> FlowResult:
        """Handle a reauthorization flow request."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        errors = None
        assert self._reauth_entry
        if user_input is not None:
            user_input = {**self._reauth_entry.data, **user_input}
            if not (
                errors := await self.hass.async_add_executor_job(
                    validate_input, user_input
                )
            ):
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry, data=user_input
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            description_placeholders={
                CONF_USERNAME: self._reauth_entry.data[CONF_USERNAME]
            },
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
