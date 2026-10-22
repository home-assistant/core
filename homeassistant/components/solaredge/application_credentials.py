"""SolarEdge Site Access application credentials."""

import asyncio
import secrets
import time
from typing import override

from aiohttp import ClientError, RequestInfo
from aiosolaredge.v2 import RateLimitError
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestConnectionError,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import _encode_jwt
from homeassistant.helpers.network import get_url

from .const import DOMAIN
from .oauth_callback import CALLBACK_PATH, STATE_LIFETIME
from .v2_budget import get_budget

AUTHORIZE_URL = "https://connect.solaredge.com/authorize"
TOKEN_URL = "https://monitoringapi.solaredge.com/v2/oauth2/token"


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> AuthImplementation:
    """Use JSON for code exchange and refresh, preserving HA's signed state."""
    return SolarEdgeAuthImplementation(
        hass,
        auth_domain,
        credential,
        authorization_server=AuthorizationServer(
            authorize_url=AUTHORIZE_URL, token_url=TOKEN_URL
        ),
    )


def _check_status(status: int) -> None:
    """Map status without retaining request bodies, headers or provider messages."""
    request_info = RequestInfo(URL(TOKEN_URL), "POST", CIMultiDictProxy(CIMultiDict()))
    if status == 429 or status >= 500:
        raise OAuth2TokenRequestTransientError(
            domain=DOMAIN, request_info=request_info, status=status
        )
    if 400 <= status < 500:
        raise OAuth2TokenRequestReauthError(
            domain=DOMAIN, request_info=request_info, status=status
        )
    if status != 200:
        raise OAuth2TokenRequestConnectionError(domain=DOMAIN)


class SolarEdgeAuthImplementation(AuthImplementation):
    """Provider-specific JSON transport with redacted failures."""

    @property
    @override
    def redirect_uri(self) -> str:
        """Use this instance's existing HTTPS callback, not a shared relay."""
        return (
            get_url(
                self.hass,
                require_ssl=True,
                allow_internal=False,
                allow_cloud=False,
                prefer_external=True,
            ).rstrip("/")
            + CALLBACK_PATH
        )

    @override
    async def async_generate_authorize_url(self, flow_id: str) -> str:
        """Carry the same expiring HA-signed state in both provider parameters."""
        url = URL(await super().async_generate_authorize_url(flow_id))
        state = _encode_jwt(
            self.hass,
            {
                "flow_id": flow_id,
                "redirect_uri": url.query["redirect_uri"],
                "exp": int(time.time()) + STATE_LIFETIME,
                "nonce": secrets.token_urlsafe(32),
            },
        )
        return str(url.update_query(state=state, external_id=state))

    @property
    @override
    def extra_authorize_data(self) -> dict[str, str]:
        """Request only site-level data for the Basic site sensors."""
        return {"scope": "SITE_DATA DEVICE_DATA"}

    @override
    async def _token_request(self, data: dict) -> dict:
        """Exchange or rotate tokens without logging secrets or response bodies."""
        budget = get_budget(self.hass)
        try:
            await budget.reserve()
        except RateLimitError:
            _check_status(429)
        session = async_get_clientsession(self.hass)
        try:
            async with asyncio.timeout(30):
                async with session.post(
                    self.token_url,
                    json={
                        **data,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                    allow_redirects=False,
                ) as response:
                    if response.status == 429:
                        await budget.pause(
                            RateLimitError(
                                response.headers.get("Retry-After"), http_status=429
                            )
                        )
                    _check_status(response.status)
                    result = await response.json()
        except OAuth2TokenRequestReauthError, OAuth2TokenRequestTransientError:
            raise
        except ClientError, TimeoutError, ValueError:
            raise OAuth2TokenRequestConnectionError(domain=DOMAIN) from None

        if (
            not isinstance(result, dict)
            or not isinstance(result.get("access_token"), str)
            or not result["access_token"]
            or not isinstance(result.get("refresh_token"), str)
            or not result["refresh_token"]
            or not isinstance(result.get("token_type"), str)
            or result["token_type"].lower() != "bearer"
            or not isinstance(result.get("expires_in"), int)
            or isinstance(result["expires_in"], bool)
            or result["expires_in"] <= 0
        ):
            raise OAuth2TokenRequestConnectionError(domain=DOMAIN)

        # Do not pass arbitrary provider data to generic helpers which may log it.
        return {
            key: result[key]
            for key in ("access_token", "refresh_token", "expires_in", "token_type")
        }
