"""Config flow for Geocaching."""

from collections.abc import Mapping
import logging
from typing import Any, override

from geocachingapi.geocachingapi import GeocachingApi
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import CONF_CACHE_CODES, DOMAIN, ENVIRONMENT, MAX_TRACKED_CACHES


class GeocachingFlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle Geocaching OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowWithReload:
        """Create the options flow."""
        return GeocachingOptionsFlow()

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an oauth config entry or update existing entry for reauth."""
        api = GeocachingApi(
            environment=ENVIRONMENT,
            token=data["token"]["access_token"],
            session=async_get_clientsession(self.hass),
        )
        status = await api.update()
        if not status.user or not status.user.username:
            return self.async_abort(reason="oauth_error")

        if existing_entry := await self.async_set_unique_id(
            status.user.username.lower()
        ):
            self.hass.config_entries.async_update_entry(existing_entry, data=data)
            await self.hass.config_entries.async_reload(existing_entry.entry_id)
            return self.async_abort(reason="reauth_successful")
        return self.async_create_entry(title=status.user.username, data=data)


class GeocachingOptionsFlow(OptionsFlowWithReload):
    """Handle Geocaching options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage Geocaching options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            raw_codes = user_input.get(CONF_CACHE_CODES, "")

            cache_codes = [
                code.strip().upper()
                for code in raw_codes.replace(",", "\n").splitlines()
                if code.strip()
            ]

            # Remove duplicates while preserving the entered order.
            cache_codes = list(dict.fromkeys(cache_codes))

            if len(cache_codes) > MAX_TRACKED_CACHES:
                errors["base"] = "too_many_caches"
            else:
                return self.async_create_entry(data={CONF_CACHE_CODES: cache_codes})

        current_codes = self.config_entry.options.get(CONF_CACHE_CODES, [])

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_CACHE_CODES,
                        default="\n".join(current_codes),
                    ): str
                }
            ),
            errors=errors,
        )
