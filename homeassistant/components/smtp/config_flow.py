"""Config flow for smtp integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from smtplib import SMTPAuthenticationError
import socket
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RECIPIENT,
    CONF_SENDER,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from . import get_smtp_client
from .const import (
    CONF_DEBUG,
    CONF_ENCRYPTION,
    CONF_SENDER_NAME,
    CONF_SERVER,
    DEFAULT_DEBUG,
    DEFAULT_ENCRYPTION,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    ENCRYPTION_OPTIONS,
)

# pylint: disable=no-value-for-parameter
RECEPIENTS_SCHEMA = vol.Schema(vol.All(cv.ensure_list_csv, [vol.Email()]))

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_SENDER): str,
        vol.Optional(CONF_SENDER_NAME): str,
        vol.Required(CONF_RECIPIENT): str,
        vol.Optional(CONF_SERVER, default=DEFAULT_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_ENCRYPTION, default=DEFAULT_ENCRYPTION): vol.In(
            ENCRYPTION_OPTIONS
        ),
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
        vol.Optional(CONF_DEBUG, default=DEFAULT_DEBUG): bool,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
    }
)

_LOGGER = logging.getLogger(__name__)


def validate_input(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate user input."""
    errors: dict[str, str] = {}
    try:
        # pylint: disable=no-value-for-parameter
        vol.Email()(user_input[CONF_SENDER])
    except vol.Invalid:
        errors[CONF_SENDER] = "invalid_email"

    try:
        RECEPIENTS_SCHEMA(user_input[CONF_RECIPIENT])
    except vol.Invalid:
        errors[CONF_RECIPIENT] = "invalid_email"

    if not errors:
        try:
            smtp_client = get_smtp_client(user_input)
            smtp_client.quit()

        except SMTPAuthenticationError:
            errors[CONF_USERNAME] = errors[CONF_PASSWORD] = "invalid_auth"

        except (socket.gaierror, ConnectionRefusedError, OSError):
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

            await self.async_set_unique_id(user_input[CONF_SENDER])
            self._abort_if_unique_id_configured()

            self._async_abort_entries_match(
                {
                    CONF_NAME: user_input[CONF_NAME],
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

    async def async_step_reauth(
        self, data: Mapping[str, Any] | None = None
    ) -> FlowResult:
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
