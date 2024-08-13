"""Handle Yale connection setup and authentication."""

from http import HTTPStatus
import logging
from pathlib import Path

from aiohttp import ClientError, ClientSession
from aiohttp.client_exceptions import ClientResponseError
from yalexs.authenticator_common import Authentication, AuthenticationState
from yalexs.manager.exceptions import CannotConnect, InvalidAuth
from yalexs.manager.gateway import Gateway

from homeassistant.helpers import config_entry_oauth2_flow

_LOGGER = logging.getLogger(__name__)


class YaleGateway(Gateway):
    """Handle the connection to Yale."""

    def __init__(
        self,
        config_path: Path,
        aiohttp_session: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Init the connection."""
        super().__init__(config_path, aiohttp_session)
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Get access token."""
        return self._oauth_session.token["access_token"]

    async def async_refresh_access_token_if_needed(self) -> None:
        """Refresh the access token if needed."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()
            self._async_setup_authentication()

    async def async_authenticate(self) -> Authentication:
        """Authenticate with the details provided to setup."""
        try:
            await self._oauth_session.async_ensure_token_valid()
        except ClientResponseError as ex:
            if ex.status == HTTPStatus.UNAUTHORIZED:
                raise InvalidAuth from ex
            raise CannotConnect from ex
        except ClientError as ex:
            raise CannotConnect from ex
        self._async_setup_authentication()

    def _async_setup_authentication(self) -> Authentication:
        token = self._oauth_session.token
        access_token = token["access_token"]
        self.authentication = Authentication(
            AuthenticationState.AUTHENTICATED, None, access_token, None
        )
        return self.authentication
