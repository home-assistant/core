"""Config flow for Spotify."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from spotipy import Spotify

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN, SPOTIFY_SCOPES


class SpotifyFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Spotify OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = 1

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": ",".join(SPOTIFY_SCOPES)}

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for Spotify."""
        spotify = Spotify(auth=data["token"]["access_token"])

        try:
            current_user = await self.hass.async_add_executor_job(spotify.current_user)
        except Exception:  # noqa: BLE001
            return self.async_abort(reason="connection_error")

        name = data["id"] = current_user["id"]

        if current_user.get("display_name"):
            name = current_user["display_name"]
        data["name"] = name

        await self.async_set_unique_id(current_user["id"])

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="reauth_account_mismatch")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), title=name, data=data
            )
        return self.async_create_entry(title=name, data=data)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon migration of old entries."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        reauth_entry = self._get_reauth_entry()
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                description_placeholders={"account": reauth_entry.data["id"]},
                errors={},
            )

        return await self.async_step_pick_implementation(
            user_input={"implementation": reauth_entry.data["auth_implementation"]}
        )
