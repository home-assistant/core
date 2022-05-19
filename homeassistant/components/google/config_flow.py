"""Config flow for Google integration."""
from __future__ import annotations

import logging
from typing import Any

from oauth2client.client import Credentials

from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .api import (
    DEVICE_AUTH_CREDS,
    DeviceAuth,
    DeviceFlow,
    OAuthError,
    async_create_device_flow,
    get_feature_access,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Google Calendars OAuth2 authentication."""

    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Set up instance."""
        super().__init__()
        self._reauth = False
        self._device_flow: DeviceFlow | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_import(self, info: dict[str, Any]) -> FlowResult:
        """Import existing auth into a new config entry."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        implementations = await config_entry_oauth2_flow.async_get_implementations(
            self.hass, self.DOMAIN
        )
        assert len(implementations) == 1
        self.flow_impl = list(implementations.values())[0]
        self.external_data = info
        return await super().async_step_creation(info)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle external yaml configuration."""
        if not self._reauth and self._async_current_entries():
            return self.async_abort(reason="already_configured")
        return await super().async_step_user(user_input)

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Create an entry for auth."""
        # The default behavior from the parent class is to redirect the
        # user with an external step. When using the device flow, we instead
        # prompt the user to visit a URL and enter a code. The device flow
        # background task will poll the exchange endpoint to get valid
        # creds or until a timeout is complete.
        if user_input is not None:
            return self.async_show_progress_done(next_step_id="creation")

        if not self._device_flow:
            _LOGGER.debug("Creating DeviceAuth flow")
            if not isinstance(self.flow_impl, DeviceAuth):
                _LOGGER.error(
                    "Unexpected OAuth implementation does not support device auth: %s",
                    self.flow_impl,
                )
                return self.async_abort(reason="oauth_error")
            try:
                device_flow = await async_create_device_flow(
                    self.hass,
                    self.flow_impl.client_id,
                    self.flow_impl.client_secret,
                    get_feature_access(self.hass),
                )
            except OAuthError as err:
                _LOGGER.error("Error initializing device flow: %s", str(err))
                return self.async_abort(reason="oauth_error")
            self._device_flow = device_flow

            async def _exchange_finished(creds: Credentials | None) -> None:
                self.external_data = {
                    DEVICE_AUTH_CREDS: creds
                }  # is None on timeout/expiration
                self.hass.async_create_task(
                    self.hass.config_entries.flow.async_configure(
                        flow_id=self.flow_id, user_input={}
                    )
                )

            await device_flow.start_exchange_task(_exchange_finished)

        return self.async_show_progress(
            step_id="auth",
            description_placeholders={
                "url": self._device_flow.verification_url,
                "user_code": self._device_flow.user_code,
            },
            progress_action="exchange",
        )

    async def async_step_creation(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle external yaml configuration."""
        if self.external_data.get(DEVICE_AUTH_CREDS) is None:
            return self.async_abort(reason="code_expired")
        return await super().async_step_creation(user_input)

    async def async_oauth_create_entry(self, data: dict) -> FlowResult:
        """Create an entry for the flow, or update existing entry."""
        existing_entries = self._async_current_entries()
        if existing_entries:
            assert len(existing_entries) == 1
            entry = existing_entries[0]
            self.hass.config_entries.async_update_entry(entry, data=data)
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_abort(reason="reauth_successful")
        return self.async_create_entry(title=self.flow_impl.name, data=data)

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self._reauth = True
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()
