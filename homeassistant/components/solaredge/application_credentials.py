"""Application credentials for SolarEdge."""

from http import HTTPStatus
import secrets
from typing import Any, cast, override

from aiohttp import ClientError, web

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import UnknownFlow
from homeassistant.exceptions import (
    OAuth2TokenRequestConnectionError,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers import config_entry_oauth2_flow, http, oauth2
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_CALLBACK_PATH, OAUTH2_TOKEN

type PendingOAuthFlow = tuple[str, str | None]

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
    hass.data.setdefault(DATA_PENDING_OAUTH_FLOWS, {})[site_id] = (flow_id, None)


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
        if not (
            pending_flow := hass.data.get(DATA_PENDING_OAUTH_FLOWS, {}).pop(
                site_id, None
            )
        ):
            return web.Response(
                text="No matching SolarEdge authorization flow",
                status=HTTPStatus.BAD_REQUEST,
            )
        flow_id, redirect_uri = pending_flow
        if redirect_uri is None:
            return web.Response(
                text="SolarEdge authorization flow is not ready",
                status=HTTPStatus.BAD_REQUEST,
            )

        try:
            user_input: dict[str, Any] = {
                "state": {
                    "flow_id": flow_id,
                    "redirect_uri": redirect_uri,
                }
            }
            if "code" in request.query:
                user_input["code"] = request.query["code"]
            else:
                user_input["error"] = request.query["error"]
            await hass.config_entries.flow.async_configure(
                flow_id=flow_id,
                user_input=user_input,
            )
        except UnknownFlow:
            return web.Response(
                text="SolarEdge authorization flow expired",
                status=HTTPStatus.BAD_REQUEST,
            )

        return web.Response(
            headers={"content-type": "text/html"},
            text="<script>window.close()</script>",
        )


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
        for site_id, (pending_flow_id, _) in pending_flows.items():
            if pending_flow_id == flow_id:
                pending_flows[site_id] = (flow_id, redirect_uri)
                break
        else:
            raise RuntimeError("No pending SolarEdge authorization flow")
        return oauth2.build_authorize_url(
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

    @override
    async def async_resolve_external_data(self, external_data: dict[str, Any]) -> dict:
        """Resolve the authorization code using the flow's PKCE verifier."""
        flow_id = external_data["state"]["flow_id"]
        if (code_verifier := self._code_verifiers.pop(flow_id, None)) is None:
            raise OAuth2TokenRequestConnectionError(domain=self.service_domain)
        return await self._token_request(
            {
                "grant_type": "authorization_code",
                "code": external_data["code"],
                "redirect_uri": external_data["state"]["redirect_uri"],
                "code_verifier": code_verifier,
            }
        )

    @override
    async def _token_request(self, data: dict) -> dict:
        """Make a JSON token request."""
        response = None
        try:
            response = await async_get_clientsession(self.hass).post(
                self.token_url,
                json={
                    **data,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            result = cast(dict[str, Any], await response.json())
        except (ClientError, ValueError) as err:
            raise OAuth2TokenRequestConnectionError(domain=self.service_domain) from err

        if response.status < HTTPStatus.BAD_REQUEST:
            return result

        error_type = (
            OAuth2TokenRequestReauthError
            if response.status in (HTTPStatus.BAD_REQUEST, HTTPStatus.UNAUTHORIZED)
            else OAuth2TokenRequestTransientError
        )
        raise error_type(
            request_info=response.request_info,
            history=response.history,
            status=response.status,
            message=str(result.get("error_description", result.get("error", ""))),
            headers=response.headers,
            domain=self.service_domain,
        )


async def async_get_auth_implementation(
    hass: HomeAssistant,
    auth_domain: str,
    credential: ClientCredential,
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return the SolarEdge OAuth implementation."""
    if not hass.data.get(DATA_CALLBACK_REGISTERED):
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
