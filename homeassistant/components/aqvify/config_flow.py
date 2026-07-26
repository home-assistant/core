"""Config flow for the Aqvify integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from aiohttp import ClientResponseError
from pyaqvify import AqvifyAPI, AqvifyAuthException
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)


class AqvifyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aqvify."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            hub = AqvifyAPI(
                user_input[CONF_API_KEY],
                websession=async_get_clientsession(self.hass),
            )
            try:
                account_data = await hub.async_get_account_id()
            except AqvifyAuthException:
                errors["base"] = "invalid_auth"
            except ClientResponseError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(account_data.account_id)
                if self.source == SOURCE_RECONFIGURE:
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(), data_updates=user_input
                    )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=account_data.name or "Aqvify", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "aqvify_url": "https://app.aqvify.com/User",
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication confirmation."""
        errors = {}

        if user_input is not None:
            api_client = AqvifyAPI(
                user_input[CONF_API_KEY],
                websession=async_get_clientsession(self.hass),
            )
            try:
                account_data = await api_client.async_get_account_id()
            except AqvifyAuthException:
                errors["base"] = "invalid_auth"
            except ClientResponseError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(account_data.account_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates=user_input
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User initiated reconfiguration."""
        return await self.async_step_user()
