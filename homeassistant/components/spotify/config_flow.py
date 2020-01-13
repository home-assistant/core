"""Config flow for Spotify."""
import logging

from spotipy import Spotify

from homeassistant import config_entries
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class SpotifyFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Spotify OAuth2 authentication."""

    DOMAIN = DOMAIN
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        scopes = [
            # Needed to be able to control playback
            "user-modify-playback-state",
            # Needed in order to read available devices
            "user-read-playback-state",
            # Needed to determine if the user has Spotify Premium
            "user-read-private",
        ]
        return {"scope": ",".join(scopes)}

    async def async_oauth_create_entry(self, data: dict) -> dict:
        """Create an entry for Spotify."""
        spotify = Spotify(auth=data["token"]["access_token"])

        try:
            current_user = await self.hass.async_add_executor_job(spotify.current_user)
        except Exception:  # pylint: disable=broad-except
            return self.async_abort(reason="connection_error")

        name = data["id"] = current_user["id"]

        if current_user.get("display_name"):
            name = current_user["display_name"]
        data["name"] = name

        await self.async_set_unique_id(current_user["id"])

        return self.async_create_entry(title=name, data=data)
