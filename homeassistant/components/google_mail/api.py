"""API for Google Mail bound to Home Assistant OAuth."""

from functools import partial

from aiohttp.client_exceptions import ClientError, ClientResponseError
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import config_entry_oauth2_flow


class AsyncConfigEntryAuth:
    """Provide Google Mail authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        oauth2_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize Google Mail Auth."""
        self._hass = hass
        self.oauth_session = oauth2_session

    @property
    def access_token(self) -> str:
        """Return the access token."""
        return self.oauth_session.token[CONF_ACCESS_TOKEN]

    async def check_and_refresh_token(self) -> str:
        """Check the token."""
        setup_in_progress = (
            self.oauth_session.config_entry.state is ConfigEntryState.SETUP_IN_PROGRESS
        )

        try:
            await self.oauth_session.async_ensure_token_valid()
        except OAuth2TokenRequestReauthError as ex:
            if setup_in_progress:
                raise ConfigEntryAuthFailed(
                    "OAuth session is not valid, reauth required"
                ) from ex
            self.oauth_session.config_entry.async_start_reauth(self.oauth_session.hass)
            raise HomeAssistantError(ex) from ex
        except OAuth2TokenRequestError as ex:
            if setup_in_progress:
                raise ConfigEntryNotReady from ex
            raise HomeAssistantError(ex) from ex
        except (RefreshError, ClientResponseError, ClientError) as ex:
            if setup_in_progress:
                if isinstance(ex, ClientResponseError) and 400 <= ex.status < 500:
                    raise ConfigEntryAuthFailed(
                        "OAuth session is not valid, reauth required"
                    ) from ex
                raise ConfigEntryNotReady from ex
            status = getattr(ex, "status", None)
            if isinstance(ex, RefreshError) or (
                isinstance(status, int) and 400 <= status < 500
            ):
                self.oauth_session.config_entry.async_start_reauth(
                    self.oauth_session.hass
                )
            raise HomeAssistantError(ex) from ex
        return self.access_token

    async def get_resource(self) -> Resource:
        """Get current resource."""
        credentials = Credentials(await self.check_and_refresh_token())
        return await self._hass.async_add_executor_job(
            partial(build, "gmail", "v1", credentials=credentials)
        )
