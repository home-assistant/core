"""Config flow for Spotify."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from spotipy import Spotify

from homeassistant.config_entries import ConfigEntry
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN, SPOTIFY_SCOPES


class SpotifyFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Spotify OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = 1

    reauth_entry: ConfigEntry | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": ",".join(SPOTIFY_SCOPES)}

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> FlowResult:
        """Create an entry for Spotify."""
        spotify = Spotify(auth=data["token"]["access_token"])

        try:
            current_user = await self.hass.async_add_executor_job(spotify.current_user)
        except Exception:  # pylint: disable=broad-except
            return self.async_abort(reason="connection_error")

        name = data["id"] = current_user["id"]

        if self.reauth_entry and self.reauth_entry.data["id"] != current_user["id"]:
            return self.async_abort(reason="reauth_account_mismatch")

        if current_user.get("display_name"):
            name = current_user["display_name"]
        data["name"] = name

        await self.async_set_unique_id(current_user["id"])

        return self.async_create_entry(title=name, data=data)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon migration of old entries."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        if self.reauth_entry is None:
            return self.async_abort(reason="reauth_account_mismatch")

        if user_input is None and self.reauth_entry:
            return self.async_show_form(
                step_id="reauth_confirm",
                description_placeholders={"account": self.reauth_entry.data["id"]},
                errors={},
            )

        return await self.async_step_pick_implementation(
            user_input={"implementation": self.reauth_entry.data["auth_implementation"]}
        )
