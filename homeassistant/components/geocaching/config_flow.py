"""Config flow for Geocaching."""

from collections.abc import Mapping
import logging
import re
from typing import Any, override

from geocachingapi.geocachingapi import GeocachingApi
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_CODE
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import (
    CONF_TRACKABLE_CODES,
    DOMAIN,
    ENVIRONMENT,
    MAX_TRACKED_CACHES,
    MAX_TRACKED_TRACKABLES,
    SUBENTRY_TYPE_TRACKED_CACHE,
)


class GeocachingFlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle Geocaching OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = 1

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {
            SUBENTRY_TYPE_TRACKED_CACHE: TrackedCacheSubentryFlow,
        }

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
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


class GeocachingCodeSubentryFlow(ConfigSubentryFlow):
    """Handle a Geocaching code subentry flow."""

    code_pattern: str
    invalid_code_error: str
    max_subentries: int
    max_subentries_abort: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a Geocaching code subentry."""
        entry = self._get_entry()
        if (
            len(entry.get_subentries_of_type(self._subentry_type))
            >= self.max_subentries
        ):
            return self.async_abort(reason=self.max_subentries_abort)

        errors: dict[str, str] = {}

        if user_input is not None:
            code = user_input[CONF_CODE].strip().upper()
            if re.fullmatch(self.code_pattern, code) is None:
                errors[CONF_CODE] = self.invalid_code_error
            elif code in {
                subentry.unique_id
                for subentry in entry.get_subentries_of_type(self._subentry_type)
            }:
                errors[CONF_CODE] = "already_configured"
            else:
                return self.async_create_entry(
                    title=code,
                    data={CONF_CODE: code},
                    unique_id=code,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_CODE): str}),
            errors=errors,
        )


class TrackedCacheSubentryFlow(GeocachingCodeSubentryFlow):
    """Handle a tracked cache subentry flow."""

    code_pattern = r"GC[A-Z0-9]+"
    invalid_code_error = "invalid_cache_code"
    max_subentries = MAX_TRACKED_CACHES
    max_subentries_abort = "too_many_caches"


class GeocachingOptionsFlow(OptionsFlow):
    """Handle Geocaching options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage tracked trackables."""
        errors: dict[str, str] = {}

        if user_input is not None:
            raw_codes = user_input.get(CONF_TRACKABLE_CODES, "")
            trackable_codes = [
                code.strip().upper()
                for code in raw_codes.replace(",", "\n").splitlines()
                if code.strip()
            ]
            trackable_codes = list(dict.fromkeys(trackable_codes))

            if len(trackable_codes) > MAX_TRACKED_TRACKABLES:
                errors["base"] = "too_many_trackables"
            elif any(
                re.fullmatch(r"TB[A-Z0-9]+", code) is None for code in trackable_codes
            ):
                errors["base"] = "invalid_trackable_code"
            else:
                return self.async_create_entry(
                    data={CONF_TRACKABLE_CODES: trackable_codes}
                )

        current_codes = self.config_entry.options.get(CONF_TRACKABLE_CODES, [])
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_TRACKABLE_CODES,
                        default=", ".join(current_codes),
                    ): str
                }
            ),
            errors=errors,
        )
