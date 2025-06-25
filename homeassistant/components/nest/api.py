"""API for Google Nest Device Access bound to Home Assistant OAuth."""

from __future__ import annotations

import datetime
import logging
from typing import cast

from aiohttp import ClientSession
from google.oauth2.credentials import Credentials
from google_nest_sdm.admin_client import PUBSUB_API_HOST, AdminClient
from google_nest_sdm.auth import AbstractAuth
from google_nest_sdm.google_nest_subscriber import GoogleNestSubscriber

from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from .const import (
    API_URL,
    CONF_PROJECT_ID,
    CONF_SUBSCRIBER_ID,
    CONF_SUBSCRIPTION_NAME,
    OAUTH2_TOKEN,
    SDM_SCOPES,
)
from .types import NestConfigEntry

_LOGGER = logging.getLogger(__name__)


class AsyncConfigEntryAuth(AbstractAuth):
    """Provide Google Nest Device Access authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
        client_id: str,
        client_secret: str,
    ) -> None:
        """Initialize Google Nest Device Access auth."""
        super().__init__(websession, API_URL)
        self._oauth_session = oauth_session
        self._client_id = client_id
        self._client_secret = client_secret

    async def async_get_access_token(self) -> str:
        """Return a valid access token for SDM API."""
        await self._oauth_session.async_ensure_token_valid()
        return cast(str, self._oauth_session.token["access_token"])

    async def async_get_creds(self) -> Credentials:
        """Return an OAuth credential for Pub/Sub Subscriber.

        The subscriber will call this when connecting to the stream to refresh
        the token. We construct a credentials object using the underlying
        OAuth2Session since the subscriber may expect the expiry fields to
        be present.
        """
        await self.async_get_access_token()
        token = self._oauth_session.token
        creds = Credentials(  # type: ignore[no-untyped-call]
            token=token["access_token"],
            refresh_token=token["refresh_token"],
            token_uri=OAUTH2_TOKEN,
            client_id=self._client_id,
            client_secret=self._client_secret,
            scopes=SDM_SCOPES,
        )
        creds.expiry = datetime.datetime.fromtimestamp(token["expires_at"])
        return creds


class AccessTokenAuthImpl(AbstractAuth):
    """Authentication implementation used during config flow, without refresh.

    This exists to allow the config flow to use the API before it has fully
    created a config entry required by OAuth2Session. This does not support
    refreshing tokens, which is fine since it should have been just created.
    """

    def __init__(
        self,
        websession: ClientSession,
        access_token: str,
        host: str,
    ) -> None:
        """Init the Nest client library auth implementation."""
        super().__init__(websession, host)
        self._access_token = access_token

    async def async_get_access_token(self) -> str:
        """Return the access token."""
        return self._access_token

    async def async_get_creds(self) -> Credentials:
        """Return an OAuth credential for Pub/Sub Subscriber."""
        return Credentials(  # type: ignore[no-untyped-call]
            token=self._access_token,
            token_uri=OAUTH2_TOKEN,
            scopes=SDM_SCOPES,
        )


async def new_auth(hass: HomeAssistant, entry: NestConfigEntry) -> AbstractAuth:
    """Create a GoogleNestSubscriber."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    if not isinstance(
        implementation, config_entry_oauth2_flow.LocalOAuth2Implementation
    ):
        raise TypeError(f"Unexpected auth implementation {implementation}")
    return AsyncConfigEntryAuth(
        aiohttp_client.async_get_clientsession(hass),
        config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation),
        implementation.client_id,
        implementation.client_secret,
    )


async def new_subscriber(
    hass: HomeAssistant,
    entry: NestConfigEntry,
    auth: AbstractAuth,
) -> GoogleNestSubscriber:
    """Create a GoogleNestSubscriber."""
    if (subscription_name := entry.data.get(CONF_SUBSCRIPTION_NAME)) is None:
        subscription_name = entry.data[CONF_SUBSCRIBER_ID]
    return GoogleNestSubscriber(auth, entry.data[CONF_PROJECT_ID], subscription_name)


def new_subscriber_with_token(
    hass: HomeAssistant,
    access_token: str,
    project_id: str,
    subscription_name: str,
) -> GoogleNestSubscriber:
    """Create a GoogleNestSubscriber with an access token."""
    return GoogleNestSubscriber(
        AccessTokenAuthImpl(
            aiohttp_client.async_get_clientsession(hass),
            access_token,
            API_URL,
        ),
        project_id,
        subscription_name,
    )


def new_pubsub_admin_client(
    hass: HomeAssistant,
    access_token: str,
    cloud_project_id: str,
) -> AdminClient:
    """Create a Nest AdminClient with an access token."""
    return AdminClient(
        auth=AccessTokenAuthImpl(
            aiohttp_client.async_get_clientsession(hass),
            access_token,
            PUBSUB_API_HOST,
        ),
        cloud_project_id=cloud_project_id,
    )
