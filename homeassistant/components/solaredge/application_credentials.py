"""Application credentials for SolarEdge."""

from dataclasses import dataclass
from http import HTTPStatus
import secrets
import time
from typing import Any, cast, override

from aiohttp import ClientError, web
from yarl import URL

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import UnknownFlow
from homeassistant.exceptions import (
    OAuth2TokenRequestConnectionError,
    OAuth2TokenRequestError,
)
from homeassistant.helpers import config_entry_oauth2_flow, http, oauth2
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.hass_dict import HassKey

from .const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_AUTHORIZE_PATH,
    OAUTH2_CALLBACK_PATH,
    OAUTH2_TOKEN,
)


@dataclass
class PendingOAuthFlow:
    """Pending SolarEdge OAuth flow."""

    flow_id: str
    browser_nonce: str
    created_at: float
    redirect_uri: str | None = None
    authorize_url: str | None = None
    implementation: SolarEdgeOAuth2Implementation | None = None


DATA_PENDING_OAUTH_FLOWS: HassKey[dict[str, PendingOAuthFlow]] = HassKey(
    f"{DOMAIN}_pending_oauth_flows"
)
DATA_CALLBACK_REGISTERED: HassKey[bool] = HassKey(f"{DOMAIN}_oauth_callback_registered")


def _redirect_uri(hass: HomeAssistant) -> str:
    """Return the provider-specific redirect URI."""
    if hass.config.external_url:
        return f"{hass.config.external_url}{OAUTH2_CALLBACK_PATH}"
    if (req := http.current_request.get()) is not None and (
        ha_host := req.headers.get(config_entry_oauth2_flow.HEADER_FRONTEND_BASE)
    ):
        return f"{ha_host}{OAUTH2_CALLBACK_PATH}"
    raise RuntimeError("No external Home Assistant URL available")


def async_register_pending_oauth_flow(
    hass: HomeAssistant, site_id: str, flow_id: str
) -> None:
    """Register a pending flow by the site ID returned in the callback."""
    pending_flows = hass.data.setdefault(DATA_PENDING_OAUTH_FLOWS, {})
    now = time.monotonic()
    for pending_site_id, pending_flow in list(pending_flows.items()):
        if now - pending_flow.created_at >= 600:
            pending_flows.pop(pending_site_id)
    pending_flows[site_id] = PendingOAuthFlow(flow_id, secrets.token_urlsafe(32), now)


def _cookie_name(flow_id: str) -> str:
    """Return the browser-binding cookie name for a flow."""
    return f"solaredge_oauth_{flow_id}"


class SolarEdgeOAuth2AuthorizeView(http.HomeAssistantView):
    """Bind the browser before redirecting it to SolarEdge."""

    requires_auth = False
    url = OAUTH2_AUTHORIZE_PATH
    name = "api:solaredge:oauth:authorize"

    async def get(self, request: web.Request) -> web.Response:
        """Set a browser-binding cookie and redirect to SolarEdge."""
        flow_id = request.query.get("flow_id")
        pending_flow = next(
            (
                pending
                for pending in request.app[http.KEY_HASS]
                .data.get(DATA_PENDING_OAUTH_FLOWS, {})
                .values()
                if pending.flow_id == flow_id
            ),
            None,
        )
        if pending_flow is None or pending_flow.authorize_url is None:
            return web.Response(
                text="No matching SolarEdge authorization flow",
                status=HTTPStatus.BAD_REQUEST,
            )
        if time.monotonic() - pending_flow.created_at >= 600:
            return web.Response(
                text="SolarEdge authorization flow expired",
                status=HTTPStatus.BAD_REQUEST,
            )

        response = web.HTTPFound(pending_flow.authorize_url)
        response.set_cookie(
            _cookie_name(pending_flow.flow_id),
            pending_flow.browser_nonce,
            httponly=True,
            max_age=600,
            path=OAUTH2_CALLBACK_PATH,
            samesite="Lax",
            secure=pending_flow.redirect_uri is not None
            and pending_flow.redirect_uri.startswith("https://"),
        )
        return response


class SolarEdgeOAuth2CallbackView(http.HomeAssistantView):
    """Handle SolarEdge's OAuth callback, which does not return state."""

    requires_auth = False
    url = OAUTH2_CALLBACK_PATH
    name = "api:solaredge:oauth:callback"

    async def get(self, request: web.Request) -> web.Response:
        """Receive an authorization code."""
        if (
            "code" not in request.query and "error" not in request.query
        ) or "site_id" not in request.query:
            return web.Response(
                text="Missing code, error, or site_id parameter",
                status=HTTPStatus.BAD_REQUEST,
            )

        hass = request.app[http.KEY_HASS]
        site_id = request.query["site_id"]
        pending_flows = hass.data.get(DATA_PENDING_OAUTH_FLOWS, {})
        if (pending_flow := pending_flows.get(site_id)) is None:
            return web.Response(
                text="No matching SolarEdge authorization flow",
                status=HTTPStatus.BAD_REQUEST,
            )
        if time.monotonic() - pending_flow.created_at >= 600:
            pending_flows.pop(site_id)
            return web.Response(
                text="SolarEdge authorization flow expired",
                status=HTTPStatus.BAD_REQUEST,
            )
        if (
            pending_flow.redirect_uri is None
            or pending_flow.implementation is None
            or not secrets.compare_digest(
                request.cookies.get(_cookie_name(pending_flow.flow_id), ""),
                pending_flow.browser_nonce,
            )
        ):
            return web.Response(
                text="Invalid SolarEdge authorization flow",
                status=HTTPStatus.BAD_REQUEST,
            )

        if "error" in request.query:
            return web.Response(
                text="SolarEdge authorization was rejected",
                status=HTTPStatus.BAD_REQUEST,
            )

        try:
            token = await pending_flow.implementation.async_exchange_code(
                pending_flow.flow_id,
                request.query["code"],
                pending_flow.redirect_uri,
            )
            await hass.config_entries.flow.async_configure(
                flow_id=pending_flow.flow_id,
                user_input={"token": token},
            )
        except (
            OAuth2TokenRequestConnectionError,
            OAuth2TokenRequestError,
        ):
            return web.Response(
                text="SolarEdge authorization code was rejected",
                status=HTTPStatus.BAD_REQUEST,
            )
        except UnknownFlow:
            pending_flows.pop(site_id, None)
            return web.Response(
                text="SolarEdge authorization flow expired",
                status=HTTPStatus.BAD_REQUEST,
            )

        pending_flows.pop(site_id, None)
        response = web.Response(
            headers={"content-type": "text/html"},
            text="<script>window.close()</script>",
        )
        response.del_cookie(
            _cookie_name(pending_flow.flow_id), path=OAUTH2_CALLBACK_PATH
        )
        return response


class SolarEdgeOAuth2Implementation(AuthImplementation):
    """SolarEdge OAuth implementation using JSON token requests."""

    def __init__(
        self,
        hass: HomeAssistant,
        auth_domain: str,
        credential: ClientCredential,
        authorization_server: AuthorizationServer,
    ) -> None:
        """Initialize the OAuth implementation."""
        super().__init__(hass, auth_domain, credential, authorization_server)
        self._code_verifiers: dict[str, str] = {}

    @property
    @override
    def extra_authorize_data(self) -> dict[str, Any]:
        """Return extra authorization parameters."""
        return {
            "scope": "SITE_DATA DEVICE_DATA",
            "access_duration": "24",
        }

    @override
    async def async_generate_authorize_url(self, flow_id: str) -> str:
        """Generate an authorization URL with PKCE."""
        code_verifier = oauth2.generate_code_verifier(128)
        self._code_verifiers[flow_id] = code_verifier
        redirect_uri = _redirect_uri(self.hass)
        pending_flows = self.hass.data.setdefault(DATA_PENDING_OAUTH_FLOWS, {})
        for pending_flow in pending_flows.values():
            if pending_flow.flow_id == flow_id:
                pending_flow.redirect_uri = redirect_uri
                pending_flow.implementation = self
                break
        else:
            raise RuntimeError("No pending SolarEdge authorization flow")
        pending_flow.authorize_url = oauth2.build_authorize_url(
            self.authorize_url,
            client_id=self.client_id,
            redirect_uri=redirect_uri,
            state=secrets.token_urlsafe(),
            extra={
                **self.extra_authorize_data,
                "code_challenge": oauth2.compute_code_challenge(code_verifier),
                "code_challenge_method": "S256",
            },
        )
        return str(
            URL(
                redirect_uri.removesuffix(OAUTH2_CALLBACK_PATH) + OAUTH2_AUTHORIZE_PATH
            ).with_query(flow_id=flow_id)
        )

    async def async_exchange_code(
        self, flow_id: str, code: str, redirect_uri: str
    ) -> dict[str, Any]:
        """Exchange a validated callback code using the flow's PKCE verifier."""
        if (code_verifier := self._code_verifiers.get(flow_id)) is None:
            raise OAuth2TokenRequestConnectionError(domain=self.service_domain)
        token = await self._token_request(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            }
        )
        self._code_verifiers.pop(flow_id, None)
        return token

    @override
    async def async_resolve_external_data(
        self, external_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Return the token already validated by the provider callback."""
        return external_data["token"]

    @override
    async def _token_request(self, data: dict) -> dict:
        """Make a JSON token request."""
        try:
            response = await async_get_clientsession(self.hass).post(
                self.token_url,
                json={
                    **data,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            response.raise_for_status()
            result = cast(dict[str, Any], await response.json())
        except ClientError as err:
            oauth2.raise_mapped_token_error(err, self.service_domain)
        except (TimeoutError, ValueError) as err:
            raise OAuth2TokenRequestConnectionError(domain=self.service_domain) from err

        return result


async def async_get_auth_implementation(
    hass: HomeAssistant,
    auth_domain: str,
    credential: ClientCredential,
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return the SolarEdge OAuth implementation."""
    if not hass.data.get(DATA_CALLBACK_REGISTERED):
        hass.http.register_view(SolarEdgeOAuth2AuthorizeView())
        hass.http.register_view(SolarEdgeOAuth2CallbackView())
        hass.data[DATA_CALLBACK_REGISTERED] = True
    return SolarEdgeOAuth2Implementation(
        hass,
        auth_domain,
        credential,
        AuthorizationServer(
            authorize_url=OAUTH2_AUTHORIZE,
            token_url=OAUTH2_TOKEN,
        ),
    )


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Return application credential description placeholders."""
    redirect_url = (
        f"{hass.config.external_url}{OAUTH2_CALLBACK_PATH}"
        if hass.config.external_url
        else f"https://YOUR_DOMAIN:PORT{OAUTH2_CALLBACK_PATH}"
    )
    return {
        "developer_console_url": "https://developer.solaredge.com/",
        "redirect_url": redirect_url,
    }
