"""Config flow for the VelaSmart integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from velasmart import VelaSmartApiClient, VelaSmartApiError

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class VelaSmartConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for VelaSmart."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()
            try:
                await self._async_validate(user_input)
            except VelaSmartApiError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error validating VelaSmart credentials")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="VelaSmart", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm(user_input)

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauthentication."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            try:
                await self._async_validate(user_input)
            except VelaSmartApiError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error validating VelaSmart credentials")
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, **user_input}
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=entry.data.get(CONF_USERNAME)
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def _async_validate(self, user_input: dict[str, Any]) -> None:
        """Validate credentials against the cloud API."""
        client = VelaSmartApiClient(
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
            session=async_get_clientsession(self.hass),
        )
        await client.authenticate()
