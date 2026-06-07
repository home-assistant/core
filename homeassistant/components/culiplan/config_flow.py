"""Config flow for the Culiplan integration."""

from collections.abc import Mapping
import logging
from typing import Any, Final

import aiohttp

from homeassistant import config_entries
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from .const import BASE_URL, DOMAIN, OAUTH_CLIENT_ID

_LOGGER = logging.getLogger(__name__)

# Account-id lookup runs during the config-flow user journey. 10s total is
# short enough to keep the UI responsive on a flaky backend without
# falsely failing on cold-start cloud-run latency.
_ACCOUNT_ID_TIMEOUT: Final = aiohttp.ClientTimeout(total=10)


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle the Culiplan OAuth2 + reauth + reconfigure flow."""

    DOMAIN = DOMAIN
    VERSION = 1

    @property
    def logger(self) -> logging.Logger:
        """Return the logger."""
        return _LOGGER

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ensure the built-in OAuth credential exists, then start OAuth."""
        await async_import_client_credential(
            self.hass,
            DOMAIN,
            ClientCredential(client_id=OAUTH_CLIENT_ID, client_secret=""),
        )
        return await super().async_step_user(user_input)

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create or update the entry on successful OAuth.

        Three sources land here:

        * ``SOURCE_USER`` — first-time setup, create a new entry.
        * ``SOURCE_REAUTH`` — token refresh failed, update the existing
          entry's token (same account required).
        * ``SOURCE_RECONFIGURE`` — user clicked "Reconfigure", update the
          existing entry's token (same account required).
        """
        account_id = await self._fetch_account_id(data)

        if self.source == config_entries.SOURCE_REAUTH:
            return await self._async_finish_reauth(data, account_id)

        if self.source == config_entries.SOURCE_RECONFIGURE:
            return await self._async_finish_reconfigure(data, account_id)

        if account_id is not None:
            await self.async_set_unique_id(account_id)
            self._abort_if_unique_id_configured()

        return self.async_create_entry(title="Culiplan", data=data)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start the re-auth flow when the API returns 401."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the user wants to re-authenticate."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Re-run the OAuth flow against the existing entry."""
        return await self.async_step_user()

    # ─── Account helpers ─────────────────────────────────────────────────────

    async def _fetch_account_id(self, data: dict[str, Any]) -> str | None:
        """Fetch the Culiplan account id used as ``unique_id``."""
        token = data.get("token") or {}
        access_token = token.get("access_token") if isinstance(token, dict) else None
        if not access_token:
            return None
        session = aiohttp_client.async_get_clientsession(self.hass)
        try:
            async with session.get(
                f"{BASE_URL}/api/users/me",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=_ACCOUNT_ID_TIMEOUT,
            ) as resp:
                if resp.status != 200:
                    return None
                me = await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.debug("Could not fetch /api/users/me for unique_id: %s", err)
            return None
        user_id = me.get("id") if isinstance(me, dict) else None
        return str(user_id) if user_id else None

    async def _async_finish_reconfigure(
        self, data: dict[str, Any], account_id: str | None
    ) -> ConfigFlowResult:
        """Apply a reconfigure result, enforcing the same Culiplan account."""
        entry = self._get_reconfigure_entry()
        if (
            entry.unique_id is not None
            and account_id is not None
            and entry.unique_id != account_id
        ):
            return self.async_abort(reason="wrong_account")
        if account_id is not None:
            await self.async_set_unique_id(account_id)
            self._abort_if_unique_id_mismatch(reason="wrong_account")
        return self.async_update_reload_and_abort(entry, data={**entry.data, **data})

    async def _async_finish_reauth(
        self, data: dict[str, Any], account_id: str | None
    ) -> ConfigFlowResult:
        """Apply a re-auth result, enforcing the same Culiplan account.

        Without this branch, ``async_oauth_create_entry`` falls through
        to ``_abort_if_unique_id_configured`` and aborts the flow with
        ``already_configured`` — leaving the user with a stale token.
        """
        entry = self._get_reauth_entry()
        if (
            entry.unique_id is not None
            and account_id is not None
            and entry.unique_id != account_id
        ):
            return self.async_abort(reason="wrong_account")
        if account_id is not None:
            await self.async_set_unique_id(account_id)
            self._abort_if_unique_id_mismatch(reason="wrong_account")
        return self.async_update_reload_and_abort(entry, data={**entry.data, **data})
