"""Config flow for Watts Vision integration."""

from collections.abc import Mapping
import logging
from typing import Any

from visionpluspython.auth import WattsVisionAuth

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlowResult,
)
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN, OAUTH2_SCOPES


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Watts Vision OAuth2 authentication."""

    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra parameters for OAuth2 authentication."""
        return {
            "scope": " ".join(OAUTH2_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
        }

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauthentication upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")

        return await self.async_step_pick_implementation(
            user_input={
                "implementation": self._get_reauth_entry().data["auth_implementation"]
            }
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        return await self.async_step_pick_implementation(
            user_input={
                "implementation": self._get_reconfigure_entry().data[
                    "auth_implementation"
                ]
            }
        )

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for the OAuth2 flow."""

        access_token = data["token"]["access_token"]
        user_id = WattsVisionAuth.extract_user_id_from_token(access_token)

        if not user_id:
            return self.async_abort(reason="invalid_token")

        await self.async_set_unique_id(user_id)

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="account_mismatch")

            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data=data,
            )

        if self.source == SOURCE_RECONFIGURE:
            self._abort_if_unique_id_mismatch(reason="account_mismatch")

            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                data=data,
            )

        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title="Watts Vision +",
            data=data,
        )
