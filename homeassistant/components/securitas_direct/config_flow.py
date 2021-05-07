"""Config flow for securitas_direct integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from pysecuritas.core.session import ConnectionException, Session
from requests.exceptions import ConnectTimeout, HTTPError
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.const import CONF_CODE, CONF_PASSWORD, CONF_USERNAME
from .const import (
    CONF_COUNTRY,
    CONF_INSTALLATION,
    CONF_LANG,
    DOMAIN,
    MULTI_SEC_CONFIGS,
    STEP_REAUTH,
    STEP_USER,
    UNABLE_TO_CONNECT,
)


def _connect(session):
    """Connect to securitas."""

    session.connect()

    return True


class SecuritasConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for securitas_direct."""

    VERSION = 1

    def __init__(self):
        """Initialize config flow."""

        self.config_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_INSTALLATION): str,
                vol.Optional(CONF_COUNTRY, default="ES"): str,
                vol.Optional(CONF_LANG, default="es"): str,
                vol.Optional(CONF_CODE, default=None): int,
            }
        )

    async def connect(self, step_id, config):
        """Handle securitas direct login."""

        uid = config[CONF_INSTALLATION]
        try:
            session = Session(
                config[CONF_USERNAME],
                config[CONF_PASSWORD],
                uid,
                config[CONF_COUNTRY],
                config[CONF_LANG],
            )
            await self.hass.async_add_executor_job(_connect, session)
        except (ConnectionException, ConnectTimeout, HTTPError):
            return self.async_show_form(
                step_id=step_id,
                data_schema=self.config_schema,
                errors={"base": UNABLE_TO_CONNECT},
            )

        return self.async_create_entry(title=uid, data=config)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        if self._async_current_entries():
            return self.async_abort(reason=MULTI_SEC_CONFIGS)

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=self.config_schema)

        return await self.connect(STEP_USER, user_input)

    async def async_step_reauth(self, config):
        """Reauthenticate."""

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Confirm reauthenticate."""

        if user_input is None:
            return self.async_show_form(
                step_id=STEP_REAUTH, data_schema=self.config_schema
            )

        return await self.connect(STEP_REAUTH, user_input)
