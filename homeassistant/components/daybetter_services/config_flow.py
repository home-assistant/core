"""Config flow for DayBetter integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_BASE_URL, CONF_TOKEN, CONF_USER_CODE, DOMAIN

_LOGGER = logging.getLogger(__name__)


DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USER_CODE): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DayBetter."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            user_code = user_input[CONF_USER_CODE]

            # Use aiohttp to call the DayBetter authorization interface
            session = async_get_clientsession(self.hass)
            try:
                # DayBetter's interface for obtaining tokens
                resp = await session.post(
                    API_BASE_URL + "hass/integrate", json={"hassCode": user_code}
                )

                if resp.status == 200:
                    data = await resp.json()
                    if (
                        data.get("code") == 1
                        and data.get("data")
                        and data["data"].get("hassCodeToken")
                    ):
                        # Save information such as tokens
                        token = data["data"]["hassCodeToken"]
                        new_data = user_input.copy()
                        new_data[CONF_TOKEN] = token

                        _LOGGER.info("DayBetter auth OK")
                        # Save information such as tokens and refresh_token
                        return self.async_create_entry(
                            title="DayBetter Services", data=new_data
                        )
                    _LOGGER.error("DayBetter auth failed: %s", data)
                    errors["base"] = "auth_failed"
                else:
                    errors["base"] = "auth_failed"
            except aiohttp.ClientError as ex:
                _LOGGER.error("Client error during DayBetter auth: %s", ex)
                errors["base"] = "connection_error"
            except Exception as ex:
                _LOGGER.exception("Unexpected error during DayBetter auth: %s", ex)
                errors["base"] = "connection_error"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle reauth flow."""
        return await self.async_step_reauth_confirm(user_input)

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle reauth confirmation."""
        errors = {}

        if user_input is not None:
            user_code = user_input[CONF_USER_CODE]

            # Use aiohttp to call the DayBetter authorization interface
            session = async_get_clientsession(self.hass)
            try:
                # DayBetter's interface for obtaining tokens
                resp = await session.post(
                    API_BASE_URL + "hass/integrate", json={"hassCode": user_code}
                )

                if resp.status == 200:
                    data = await resp.json()
                    if (
                        data.get("code") == 1
                        and data.get("data")
                        and data["data"].get("hassCodeToken")
                    ):
                        # Save information such as tokens
                        token = data["data"]["hassCodeToken"]
                        new_data = user_input.copy()
                        new_data[CONF_TOKEN] = token

                        _LOGGER.info("DayBetter reauth OK")
                        # Update existing entry
                        existing_entry = self._reauth_entry
                        self.hass.config_entries.async_update_entry(
                            existing_entry, data=new_data
                        )
                        await self.hass.config_entries.async_reload(
                            existing_entry.entry_id
                        )
                        return self.async_abort(reason="reauth_successful")
                    _LOGGER.error("DayBetter reauth failed: %s", data)
                    errors["base"] = "auth_failed"
                else:
                    errors["base"] = "auth_failed"
            except aiohttp.ClientError as ex:
                _LOGGER.error("Client error during DayBetter reauth: %s", ex)
                errors["base"] = "connection_error"
            except Exception as ex:
                _LOGGER.exception("Unexpected error during DayBetter reauth: %s", ex)
                errors["base"] = "connection_error"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=DATA_SCHEMA,
            errors=errors,
            description_placeholders={"title": self._reauth_entry.title},
        )

    async def async_step_import(
        self, import_data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_user(import_data)

    async def async_step_user_import(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_user(user_input)
