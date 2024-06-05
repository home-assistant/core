"""API for Aladdin Connect Genie bound to Home Assistant OAuth."""

from typing import cast

from aiohttp import ClientSession
from genie_partner_sdk.auth import Auth

from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

API_URL = "https://twdvzuefzh.execute-api.us-east-2.amazonaws.com/v1"
API_KEY = "k6QaiQmcTm2zfaNns5L1Z8duBtJmhDOW8JawlCC3"


class AsyncConfigEntryAuth(Auth):  # type: ignore[misc]
    """Provide Aladdin Connect Genie authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: OAuth2Session,
    ) -> None:
        """Initialize Aladdin Connect Genie auth."""
        super().__init__(
            websession, API_URL, oauth_session.token["access_token"], API_KEY
        )
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        await self._oauth_session.async_ensure_token_valid()

        return cast(str, self._oauth_session.token["access_token"])
