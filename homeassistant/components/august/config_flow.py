"""Config flow for August integration."""

from collections.abc import Mapping
import logging
from typing import Any

import jwt

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class AugustConfigFlow(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle a config flow for August."""

    VERSION = 1
    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return _LOGGER

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_user()

    def _async_decode_jwt(self, encoded: str) -> dict[str, Any]:
        """Decode JWT token."""
        return jwt.decode(
            encoded,
            "",
            verify=False,
            options={"verify_signature": False},
            algorithms=["HS256"],
        )

    async def _async_handle_reauth(
        self, data: dict, decoded: dict[str, Any], user_id: str
    ) -> ConfigFlowResult:
        """Handle reauth flow."""
        reauth_entry = self._get_reauth_entry()
        assert reauth_entry.unique_id is not None
        # Check if this is a migration from username (contains @) to user ID
        if "@" not in reauth_entry.unique_id:
            # This is a normal oauth reauth, enforce ID matching for security
            await self.async_set_unique_id(user_id)
            self._abort_if_unique_id_mismatch(reason="reauth_invalid_user")
            return self.async_update_reload_and_abort(reauth_entry, data=data)

        # This is a one-time migration from username to user ID
        # Only validate if the account has emails
        emails: list[str]
        if emails := decoded.get("email", []):
            # Validate that the email matches before allowing migration
            email_to_check_lower = reauth_entry.unique_id.casefold()
            if not any(email.casefold() == email_to_check_lower for email in emails):
                # Email doesn't match - this is a different account
                return self.async_abort(reason="reauth_invalid_user")

        # Email matches or no emails on account, update with new unique ID
        return self.async_update_reload_and_abort(
            reauth_entry, data=data, unique_id=user_id
        )

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create an entry for the flow."""
        # Decode JWT once
        access_token = data["token"]["access_token"]
        decoded = self._async_decode_jwt(access_token)
        user_id = decoded["userId"]

        if self.source == SOURCE_REAUTH:
            return await self._async_handle_reauth(data, decoded, user_id)

        await self.async_set_unique_id(user_id)
        self._abort_if_unique_id_configured()
        return await super().async_oauth_create_entry(data)
