"""Application credentials platform for SwitchBot."""

from typing import Any, override

from aiohttp import RequestInfo
from multidict import CIMultiDict, CIMultiDictProxy
from switchbot import (
    OAUTH_AUTHORIZE_URL,
    OAUTH_SCOPE,
    OAUTH_TOKEN_URL,
    SwitchbotAccountConnectionError,
    SwitchbotApiError,
    SwitchbotAuthenticationError,
    exchange_oauth_code,
)
from yarl import URL

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    MY_AUTH_CALLBACK_PATH,
    AbstractOAuth2Implementation,
)

from .const import DOMAIN


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> AbstractOAuth2Implementation:
    """Return the SwitchBot OAuth implementation."""
    return SwitchbotOAuth2Implementation(
        hass,
        auth_domain,
        credential,
        AuthorizationServer(OAUTH_AUTHORIZE_URL, OAUTH_TOKEN_URL),
    )


def _oauth_request_info() -> RequestInfo:
    """Return request metadata for HA OAuth exception adaptation."""
    url = URL(OAUTH_TOKEN_URL)
    return RequestInfo(url, "POST", CIMultiDictProxy(CIMultiDict()), url)


class SwitchbotOAuth2Implementation(AuthImplementation):
    """SwitchBot OAuth implementation with its registered callback URI."""

    @property
    @override
    def redirect_uri(self) -> str:
        """Return the callback URI registered for the public client."""
        return MY_AUTH_CALLBACK_PATH

    @property
    @override
    def extra_authorize_data(self) -> dict[str, str]:
        """Return additional authorization parameters."""
        return {"scope": OAUTH_SCOPE}

    @override
    async def async_resolve_external_data(
        self, external_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Resolve the callback through pySwitchbot's OAuth implementation."""
        try:
            token = await exchange_oauth_code(
                async_get_clientsession(self.hass),
                self.client_id,
                external_data["state"]["redirect_uri"],
                external_data["code"],
            )
        except SwitchbotAuthenticationError as err:
            # OAuth2TokenRequestReauthError provides its own translation.
            # pylint: disable-next=home-assistant-exception-not-translated
            raise OAuth2TokenRequestReauthError(
                request_info=_oauth_request_info(),
                status=401,
                domain=DOMAIN,
            ) from err
        except SwitchbotAccountConnectionError as err:
            # OAuth2TokenRequestTransientError provides its own translation.
            # pylint: disable-next=home-assistant-exception-not-translated
            raise OAuth2TokenRequestTransientError(
                request_info=_oauth_request_info(),
                status=503,
                domain=DOMAIN,
            ) from err
        except SwitchbotApiError:
            return {}

        # The shared OAuth flow logs the full mapping when expires_in is missing.
        if "expires_in" not in token:
            return {}
        return token
