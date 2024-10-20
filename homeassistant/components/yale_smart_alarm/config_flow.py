"""Adds config flow for Yale Smart Alarm integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from yalesmartalarmclient.client import YaleSmartAlarmClient
from yalesmartalarmclient.exceptions import AuthenticationError

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_AREA_ID,
    CONF_LOCK_CODE_DIGITS,
    DEFAULT_AREA_ID,
    DEFAULT_LOCK_CODE_DIGITS,
    DEFAULT_NAME,
    DOMAIN,
    LOGGER,
    YALE_BASE_ERRORS,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_AREA_ID, default=DEFAULT_AREA_ID): cv.string,
    }
)

DATA_SCHEMA_AUTH = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


class YaleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Yale integration."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> YaleOptionsFlowHandler:
        """Get the options flow for this handler."""
        return YaleOptionsFlowHandler(config_entry)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle initiation of re-authentication with Yale."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors = {}

        if user_input is not None:
            reauth_entry = self._get_reauth_entry()
            username = reauth_entry.data[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            try:
                await self.hass.async_add_executor_job(
                    YaleSmartAlarmClient, username, password
                )
            except AuthenticationError as error:
                LOGGER.error("Authentication failed. Check credentials %s", error)
                errors = {"base": "invalid_auth"}
            except YALE_BASE_ERRORS as error:
                LOGGER.error("Connection to API failed %s", error)
                errors = {"base": "cannot_connect"}

            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=DATA_SCHEMA_AUTH,
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            name = DEFAULT_NAME
            area = user_input.get(CONF_AREA_ID, DEFAULT_AREA_ID)

            try:
                await self.hass.async_add_executor_job(
                    YaleSmartAlarmClient, username, password
                )
            except AuthenticationError as error:
                LOGGER.error("Authentication failed. Check credentials %s", error)
                errors = {"base": "invalid_auth"}
            except YALE_BASE_ERRORS as error:
                LOGGER.error("Connection to API failed %s", error)
                errors = {"base": "cannot_connect"}

            if not errors:
                await self.async_set_unique_id(username)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=username,
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_NAME: name,
                        CONF_AREA_ID: area,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )


class YaleOptionsFlowHandler(OptionsFlow):
    """Handle Yale options."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize Yale options flow."""
        self.entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage Yale options."""
        errors: dict[str, Any] = {}

        if user_input:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_LOCK_CODE_DIGITS,
                        description={
                            "suggested_value": self.entry.options.get(
                                CONF_LOCK_CODE_DIGITS, DEFAULT_LOCK_CODE_DIGITS
                            )
                        },
                    ): int,
                }
            ),
            errors=errors,
        )
