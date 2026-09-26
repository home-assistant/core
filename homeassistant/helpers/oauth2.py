"""OAuth 2.0 helpers that do not depend on config entries."""

import base64
from collections.abc import Mapping
import hashlib
from http import HTTPStatus
import json
import logging
import secrets
from typing import Any, Literal, NoReturn, cast
from urllib.parse import quote_plus

from aiohttp import ClientError, ClientResponseError, client, hdrs
from multidict import CIMultiDict
from yarl import URL

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestConnectionError,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)

from .aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

type ClientAuthMethod = Literal["client_secret_basic", "client_secret_post"]


def client_auth(
    data: Mapping[str, Any],
    client_id: str,
    client_secret: str | None,
    method: ClientAuthMethod = "client_secret_post",
) -> tuple[dict[str, Any], dict[str, str]]:
    """Return the token request body and headers that authenticate the client."""

    if method == "client_secret_basic" and client_secret:
        # RFC 6749 section 2.3.1 requires form encoding before base64.
        credentials = (
            f"{quote_plus(client_id, safe='')}:{quote_plus(client_secret, safe='')}"
        )
        encoded = base64.b64encode(credentials.encode()).decode()
        return dict(data), {hdrs.AUTHORIZATION: f"Basic {encoded}"}

    body = {**data, "client_id": client_id}
    if client_secret:
        body["client_secret"] = client_secret
    return body, {}


def generate_code_verifier(code_verifier_length: int = 128) -> str:
    """Generate a PKCE code verifier."""
    if not 43 <= code_verifier_length <= 128:
        msg = (
            "Parameter `code_verifier_length` must validate"
            "`43 <= code_verifier_length <= 128`."
        )
        raise ValueError(msg)
    return secrets.token_urlsafe(96)[:code_verifier_length]


def compute_code_challenge(code_verifier: str) -> str:
    """Compute the S256 PKCE code challenge."""
    if not 43 <= len(code_verifier) <= 128:
        msg = (
            "Parameter `code_verifier` must validate `43 <= len(code_verifier) <= 128`."
        )
        raise ValueError(msg)

    hashed = hashlib.sha256(code_verifier.encode("ascii")).digest()
    encoded = base64.urlsafe_b64encode(hashed)
    return encoded.decode("ascii").replace("=", "")


def build_authorize_url(
    authorize_url: str,
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
    extra: Mapping[str, Any] | None = None,
) -> str:
    """Return the URL that sends the user to the authorization endpoint."""
    return str(
        URL(authorize_url)
        .update_query(
            {
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "state": state,
            }
        )
        .update_query(extra or {})
    )


def raise_mapped_token_error(err: ClientError, domain: str) -> NoReturn:
    """Re-raise a failed token request as the matching OAuth2 token error."""
    if not isinstance(err, ClientResponseError):
        # Nothing was received, so there is no status to tell the causes apart.
        _LOGGER.debug("Token request for %s got no response: %s", domain, err)
        raise OAuth2TokenRequestConnectionError(domain=domain) from err

    kwargs: dict[str, Any] = {
        "request_info": err.request_info,
        "history": err.history,
        "status": err.status,
        "message": err.message,
        "headers": err.headers,
        "domain": domain,
    }
    if err.status == HTTPStatus.TOO_MANY_REQUESTS or 500 <= err.status <= 599:
        raise OAuth2TokenRequestTransientError(**kwargs) from err
    if 400 <= err.status <= 499:
        raise OAuth2TokenRequestReauthError(**kwargs) from err
    raise OAuth2TokenRequestError(**kwargs) from err


async def async_token_request(
    hass: HomeAssistant,
    token_url: str,
    data: Mapping[str, Any],
    *,
    domain: str,
    headers: Mapping[str, str] | None = None,
    allow_redirects: bool = True,
) -> dict:
    """Post to a token endpoint and return the decoded response."""
    session = async_get_clientsession(hass)

    _LOGGER.debug("Sending token request to %s", token_url)

    try:
        resp = await session.post(
            token_url, data=data, headers=headers, allow_redirects=allow_redirects
        )
        if resp.status >= 400:
            error_body = ""
            try:
                error_body = await resp.text()
                error_data = json.loads(error_body)
                error_code = error_data.get("error", "unknown error")
                error_description = error_data.get("error_description")
                detail = (
                    f"{error_code}: {error_description}"
                    if error_description
                    else error_code
                )
            except ClientError, ValueError, AttributeError:
                detail = error_body[:200] if error_body else "unknown error"
            _LOGGER.debug(
                "Token request for %s failed (%s): %s", domain, resp.status, detail
            )
        elif not allow_redirects and 300 <= resp.status < 400:
            raise ClientResponseError(
                resp.request_info,
                resp.history,
                status=resp.status,
                message="Token endpoint redirected",
                headers=resp.headers,
            )
        resp.raise_for_status()
        return cast(dict, await resp.json())
    except ClientError as err:
        # Bare TimeoutError is left alone so an enclosing asyncio.timeout applies.
        raise_mapped_token_error(err, domain)


async def async_oauth2_request(
    hass: HomeAssistant, token: dict, method: str, url: str, **kwargs: Any
) -> client.ClientResponse:
    """Make an OAuth2 authenticated request without refreshing the token."""
    session = async_get_clientsession(hass)
    headers = CIMultiDict(kwargs.pop("headers", {}))
    headers[hdrs.AUTHORIZATION] = f"Bearer {token['access_token']}"
    return await session.request(method, url, **kwargs, headers=headers)
