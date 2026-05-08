"""Config flow for the Yoto integration."""

from collections.abc import Mapping
import logging
from typing import Any

import aiohttp

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import _LOGGER, DOMAIN

FAMILY_ENDPOINT = "https://api.yotoplay.com/user/family"


class YotoOAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Authorize Home Assistant with a Yoto account using OAuth2."""

    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return the logger used for the OAuth2 flow."""
        return _LOGGER

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Resolve the Yoto family for the authenticated account."""
        access_token = data["token"]["access_token"]
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                FAMILY_ENDPOINT,
                headers={"Authorization": f"Bearer {access_token}"},
            ) as response:
                if response.status in (401, 403):
                    return self.async_abort(reason="oauth_unauthorized")
                response.raise_for_status()
                payload = await response.json()
        except aiohttp.ClientError:
            _LOGGER.exception("Could not load Yoto account family")
            return self.async_abort(reason="connection_error")

        family_id = (payload.get("family") or {}).get("familyId")
        if not family_id:
            return self.async_abort(reason="no_family")

        await self.async_set_unique_id(family_id)

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="account_mismatch")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data=data,
            )

        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Yoto", data=data)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Trigger the OAuth flow when the stored token is rejected."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthorization before opening the browser flow."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()
