"""Reauth flow for Hisense AC Plugin."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class HisenseReauthFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle reauth flow for Hisense AC Plugin."""

    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Initialize reauth flow."""
        super().__init__()
        self._reauth_entry: config_entries.ConfigEntry | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return _LOGGER

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {}

    async def async_step_reauth(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle reauth flow."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauth flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
                description_placeholders={
                    "message": "Your Hisense AC Plugin credentials have expired. Please re-authenticate to continue using the integration."
                },
            )

        # Get the OAuth2 implementation
        implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(
            self.hass, self._reauth_entry
        )

        if not implementation:
            return self.async_abort(reason="oauth2_implementation_not_available")

        self.flow_impl = implementation

        try:
            url = await self.flow_impl.async_generate_authorize_url(self.flow_id)
            return self.async_external_step(step_id="reauth", url=url)
        except Exception as err:
            _LOGGER.error("Failed to generate reauth URL: %s", err)
            return self.async_abort(reason="authorize_url_fail")

    async def async_step_reauth(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle reauth external step."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth",
                data_schema=vol.Schema({}),
                description_placeholders={
                    "message": "Please complete the authentication process in your browser."
                },
            )

        return await super().async_step_reauth(user_input)

    async def async_oauth_create_entry(self, data: dict) -> FlowResult:
        """Create an entry for the reauth flow."""
        if self._reauth_entry is None:
            return self.async_abort(reason="reauth_entry_not_found")

        # Update the existing entry with new token data
        self.hass.config_entries.async_update_entry(
            self._reauth_entry,
            data={
                **self._reauth_entry.data,
                **data,
                "auth_implementation": DOMAIN,
                "implementation": DOMAIN,
            },
        )

        # Reload the entry
        await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)

        return self.async_abort(reason="reauth_successful")


class HisenseReauthFlowManager:
    """Manager for reauth flows."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize reauth flow manager."""
        self.hass = hass

    async def async_initiate_reauth(
        self, config_entry: config_entries.ConfigEntry
    ) -> None:
        """Initiate reauth flow for a config entry."""
        _LOGGER.info("Initiating reauth for config entry: %s", config_entry.entry_id)

        # Create reauth flow
        flow = HisenseReauthFlowHandler()
        flow.hass = self.hass
        flow.context = {"entry_id": config_entry.entry_id}

        # Start the reauth flow
        await flow.async_step_reauth()

    async def async_check_reauth_required(
        self, config_entry: config_entries.ConfigEntry
    ) -> bool:
        """Check if reauth is required for a config entry."""
        try:
            # Try to get a valid token
            implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(
                self.hass, config_entry
            )

            if not implementation:
                return True

            session = config_entry_oauth2_flow.OAuth2Session(
                self.hass, config_entry, implementation
            )

            # Try to ensure token is valid
            await session.async_ensure_token_valid()
            return False

        except Exception as err:
            _LOGGER.warning("Token validation failed, reauth required: %s", err)
            return True
