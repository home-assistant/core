"""Tests for MCP OAuth dynamic client registration."""

import json
import logging
from typing import Any
from unittest.mock import Mock, patch

from aiohttp import ClientError
import httpx2
import pytest
import respx
from yarl import URL

from homeassistant.components.application_credentials import (
    DATA_COMPONENT,
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    AuthImplementation,
    AuthImplementationNotApplicable,
    AuthorizationServer,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.mcp.application_credentials import (
    McpRegisteredOAuth2Implementation,
    async_get_auth_implementation,
    authorization_server_context,
)
from homeassistant.components.mcp.const import DCR_CLIENT_NAME, DOMAIN
from homeassistant.components.mcp.registration import (
    ClientRegistrationError,
    async_register_dynamic_client,
    decode_registered_client_id,
    encode_registered_client_id,
    registered_client_auth_domain,
    resolve_registration_endpoint,
    select_token_endpoint_auth_method,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import (
    OAuth2TokenRequestConnectionError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from .conftest import (
    MCP_SERVER_URL,
    OAUTH_AUTHORIZE_URL,
    OAUTH_TOKEN_URL,
    TEST_API_NAME,
)

from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

REGISTRATION_ENDPOINT = "https://auth.example/register"
REDIRECT_URI = "https://example.com/auth/external/callback"
CALLBACK_PATH = "/auth/external/callback"
ISSUED_CLIENT_ID = "issued-client"
ISSUED_SECRET = "issued-secret"
OAUTH_DISCOVERY_ENDPOINT = (
    "http://1.1.1.1:8080/.well-known/oauth-authorization-server/mcp"
)
SCOPES = ["read", "write"]
OAUTH_TOKEN_PAYLOAD = {
    "refresh_token": "mock-refresh-token",
    "access_token": "mock-access-token",
    "type": "Bearer",
    "expires_in": 60,
}


def _server_metadata(**extra: Any) -> dict[str, Any]:
    """Return authorization server metadata, with overrides applied."""
    metadata: dict[str, Any] = {
        "authorization_endpoint": OAUTH_AUTHORIZE_URL,
        "token_endpoint": OAUTH_TOKEN_URL,
        "scopes_supported": SCOPES,
    }
    metadata.update(extra)
    return metadata


def _encoded_client(
    authorize_url: str = OAUTH_AUTHORIZE_URL,
    token_url: str = OAUTH_TOKEN_URL,
    method: str = "none",
) -> str:
    """Return a stored client id bound to an authorization server."""
    return encode_registered_client_id(
        authorize_url, token_url, ISSUED_CLIENT_ID, method
    )


async def _register(
    hass: HomeAssistant,
    response: httpx2.Response,
    methods: list[str] | None,
    scopes: Any,
) -> tuple[tuple[str, str, str], respx.Route]:
    """Post one registration response and return the issued client and route."""
    route = respx.post(REGISTRATION_ENDPOINT).mock(return_value=response)
    issued = await async_register_dynamic_client(
        hass,
        REGISTRATION_ENDPOINT,
        REDIRECT_URI,
        token_endpoint_auth_methods=methods,
        scopes=scopes,
    )
    return issued, route


async def _run_user_flow(
    hass: HomeAssistant, mock_mcp_client: Mock, metadata: dict[str, Any]
) -> config_entry_oauth2_flow.ConfigFlowResult:
    """Start a user flow that discovers the given authorization server."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=httpx2.Response(200, json=metadata)
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: MCP_SERVER_URL}
    )


def test_select_token_endpoint_auth_method() -> None:
    """Prefer public clients, then post, and default an omitted list to basic."""
    assert select_token_endpoint_auth_method(None) == "client_secret_basic"
    assert select_token_endpoint_auth_method(["client_secret_basic", "none"]) == "none"
    assert (
        select_token_endpoint_auth_method(["client_secret_basic", "client_secret_post"])
        == "client_secret_post"
    )
    assert select_token_endpoint_auth_method(["client_secret_basic"]) == (
        "client_secret_basic"
    )


@pytest.mark.parametrize("methods", [[], ["private_key_jwt"]])
def test_select_token_endpoint_auth_method_rejects_unsupported(
    methods: list[str],
) -> None:
    """Do not register when no supported auth method is advertised."""
    with pytest.raises(ClientRegistrationError):
        select_token_endpoint_auth_method(methods)


def test_registered_client_id_round_trip() -> None:
    """A registered client id decodes to the server it was issued for."""
    encoded = _encoded_client(method="client_secret_post")
    assert encoded.startswith("mcp-dcr:")
    assert decode_registered_client_id(encoded) == (
        OAUTH_AUTHORIZE_URL,
        OAUTH_TOKEN_URL,
        ISSUED_CLIENT_ID,
        "client_secret_post",
    )
    assert registered_client_auth_domain(encoded)


@pytest.mark.parametrize(
    "value",
    [
        "manual-client",
        "mcp-dcr:zz",
        "mcp-dcr:" + b"[]".hex(),
        "mcp-dcr:" + b"null".hex(),
        "mcp-dcr:" + b'"client"'.hex(),
        "mcp-dcr:" + b"{}".hex(),
        "mcp-dcr:"
        + json.dumps(
            {
                "authorize_url": "",
                "client_id": ISSUED_CLIENT_ID,
                "method": "none",
                "token_url": OAUTH_TOKEN_URL,
            }
        )
        .encode()
        .hex(),
        "mcp-dcr:"
        + json.dumps(
            {
                "authorize_url": OAUTH_AUTHORIZE_URL,
                "client_id": "",
                "method": "none",
                "token_url": OAUTH_TOKEN_URL,
            }
        )
        .encode()
        .hex(),
        "mcp-dcr:"
        + json.dumps(
            {
                "authorize_url": OAUTH_AUTHORIZE_URL,
                "client_id": ISSUED_CLIENT_ID,
                "method": "private_key_jwt",
                "token_url": OAUTH_TOKEN_URL,
            }
        )
        .encode()
        .hex(),
        "mcp-dcr:"
        + json.dumps(
            {
                "authorize_url": 1,
                "client_id": ISSUED_CLIENT_ID,
                "method": "none",
                "token_url": OAUTH_TOKEN_URL,
            }
        )
        .encode()
        .hex(),
    ],
)
def test_decode_rejects_unusable_client_ids(value: str) -> None:
    """Manual and malformed client ids are not registered clients."""
    assert decode_registered_client_id(value) is None


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        (REGISTRATION_ENDPOINT, REGISTRATION_ENDPOINT),
        ("/register", "https://auth.example/register"),
    ],
)
def test_resolve_registration_endpoint(endpoint: str, expected: str) -> None:
    """Absolute endpoints are used as advertised; relative ones are joined."""
    assert (
        resolve_registration_endpoint("https://auth.example/oauth", endpoint)
        == expected
    )


@respx.mock
async def test_register_public_client_discards_echoed_secret(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A public client is stored without a secret and the body is not logged."""
    caplog.set_level(logging.DEBUG)
    issued, route = await _register(
        hass,
        httpx2.Response(
            201,
            json={"client_id": ISSUED_CLIENT_ID, "client_secret": ISSUED_SECRET},
        ),
        ["none"],
        SCOPES,
    )
    assert issued == (ISSUED_CLIENT_ID, "", "none")
    body = json.loads(route.calls.last.request.content)
    assert body["application_type"] == "web"
    assert body["scope"] == "read write"
    assert body["token_endpoint_auth_method"] == "none"
    assert body["redirect_uris"] == [REDIRECT_URI]
    assert ISSUED_SECRET not in caplog.text


@respx.mock
async def test_register_confidential_client_with_defaults(
    hass: HomeAssistant,
) -> None:
    """An omitted auth-method list means client_secret_basic."""
    issued, _route = await _register(
        hass,
        httpx2.Response(
            200,
            json={"client_id": ISSUED_CLIENT_ID, "client_secret": ISSUED_SECRET},
        ),
        None,
        SCOPES,
    )
    assert issued == (ISSUED_CLIENT_ID, ISSUED_SECRET, "client_secret_basic")


@respx.mock
async def test_register_keeps_an_issued_auth_method(hass: HomeAssistant) -> None:
    """The method issued by the server replaces the one that was requested."""
    issued, route = await _register(
        hass,
        httpx2.Response(
            201,
            json={
                "client_id": ISSUED_CLIENT_ID,
                "client_secret": ISSUED_SECRET,
                "redirect_uris": [REDIRECT_URI],
                "token_endpoint_auth_method": "client_secret_basic",
            },
        ),
        ["client_secret_post"],
        SCOPES,
    )
    assert issued == (ISSUED_CLIENT_ID, ISSUED_SECRET, "client_secret_basic")
    body = json.loads(route.calls.last.request.content)
    assert body["token_endpoint_auth_method"] == "client_secret_post"


@pytest.mark.parametrize("scopes", ["read", [], [1]])
@respx.mock
async def test_register_omits_unusable_scopes(hass: HomeAssistant, scopes: Any) -> None:
    """A scope string is not split into characters, and an empty list is omitted."""
    _issued, route = await _register(
        hass,
        httpx2.Response(201, json={"client_id": ISSUED_CLIENT_ID}),
        ["none"],
        scopes,
    )
    assert "scope" not in json.loads(route.calls.last.request.content)


@respx.mock
async def test_register_does_not_log_the_response_body(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Registration failures log the status and not the response body."""
    caplog.set_level(logging.DEBUG)
    with pytest.raises(ClientRegistrationError):
        await _register(
            hass,
            httpx2.Response(400, text=ISSUED_SECRET),
            ["none"],
            SCOPES,
        )
    assert ISSUED_SECRET not in caplog.text
    assert "failed with status 400" in caplog.text


@pytest.mark.parametrize(
    ("methods", "response"),
    [
        (["none"], httpx2.Response(500, json={"client_id": ISSUED_CLIENT_ID})),
        (["none"], httpx2.Response(201, text=ISSUED_SECRET)),
        (["none"], httpx2.Response(201, json=["nope"])),
        (["none"], httpx2.Response(201, json={})),
        (["none"], httpx2.Response(201, json={"client_id": ""})),
        (["none"], httpx2.Response(201, json={"client_id": 5})),
        (
            ["none"],
            httpx2.Response(
                201, json={"client_id": ISSUED_CLIENT_ID, "redirect_uris": None}
            ),
        ),
        (
            ["none"],
            httpx2.Response(
                201, json={"client_id": ISSUED_CLIENT_ID, "redirect_uris": REDIRECT_URI}
            ),
        ),
        (
            ["none"],
            httpx2.Response(
                201,
                json={
                    "client_id": ISSUED_CLIENT_ID,
                    "redirect_uris": ["https://example.com/other"],
                },
            ),
        ),
        (
            ["none"],
            httpx2.Response(
                201,
                json={
                    "client_id": ISSUED_CLIENT_ID,
                    "token_endpoint_auth_method": "private_key_jwt",
                },
            ),
        ),
        (
            ["none"],
            httpx2.Response(
                201,
                json={
                    "client_id": ISSUED_CLIENT_ID,
                    "token_endpoint_auth_method": None,
                },
            ),
        ),
        (None, httpx2.Response(201, json={"client_id": ISSUED_CLIENT_ID})),
        (
            None,
            httpx2.Response(
                201, json={"client_id": ISSUED_CLIENT_ID, "client_secret": ""}
            ),
        ),
        ([], httpx2.Response(201, json={"client_id": ISSUED_CLIENT_ID})),
        (
            ["private_key_jwt"],
            httpx2.Response(201, json={"client_id": ISSUED_CLIENT_ID}),
        ),
    ],
)
@respx.mock
async def test_register_rejects_unusable_responses(
    hass: HomeAssistant, methods: list[str] | None, response: httpx2.Response
) -> None:
    """Reject a response that cannot be used as a client."""
    with pytest.raises(ClientRegistrationError):
        await _register(hass, response, methods, SCOPES)


@respx.mock
async def test_register_rejects_an_invalid_redirect_uri(hass: HomeAssistant) -> None:
    """Do not post metadata when the redirect URI is not a URL."""
    with pytest.raises(ClientRegistrationError):
        await async_register_dynamic_client(
            hass,
            REGISTRATION_ENDPOINT,
            "not a url",
            token_endpoint_auth_methods=["none"],
            scopes=None,
        )
    assert respx.calls.call_count == 0


def _implementation(
    hass: HomeAssistant, method: str, secret: str
) -> McpRegisteredOAuth2Implementation:
    """Return a registered-client implementation for token-request tests."""
    return McpRegisteredOAuth2Implementation(
        hass,
        "auth-domain",
        ISSUED_CLIENT_ID,
        OAUTH_AUTHORIZE_URL,
        OAUTH_TOKEN_URL,
        secret,
        token_endpoint_auth_method=method,
    )


def test_public_client_name_and_secret(hass: HomeAssistant) -> None:
    """Public clients use PKCE and do not keep an echoed secret."""
    implementation = _implementation(hass, "none", ISSUED_SECRET)
    assert implementation.name == DCR_CLIENT_NAME
    assert implementation.client_secret == ""
    assert implementation.client_id == ISSUED_CLIENT_ID


async def test_basic_auth_sends_the_secret_in_the_header(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """client_secret_basic authenticates with the Authorization header."""
    aioclient_mock.post(OAUTH_TOKEN_URL, json=OAUTH_TOKEN_PAYLOAD)
    implementation = _implementation(hass, "client_secret_basic", ISSUED_SECRET)
    token = await implementation.async_resolve_external_data(
        {"code": "abcd", "state": {"redirect_uri": REDIRECT_URI}}
    )
    assert token["access_token"] == OAUTH_TOKEN_PAYLOAD["access_token"]
    _method, _url, data, headers = aioclient_mock.mock_calls[0]
    assert data["client_id"] == ISSUED_CLIENT_ID
    assert "client_secret" not in data
    assert headers["Authorization"].startswith("Basic ")
    assert ISSUED_SECRET not in data.values()


async def test_post_auth_sends_the_secret_in_the_body(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """client_secret_post uses the local OAuth token request."""
    aioclient_mock.post(OAUTH_TOKEN_URL, json=OAUTH_TOKEN_PAYLOAD)
    implementation = _implementation(hass, "client_secret_post", ISSUED_SECRET)
    await implementation.async_resolve_external_data(
        {"code": "abcd", "state": {"redirect_uri": REDIRECT_URI}}
    )
    _method, _url, data, headers = aioclient_mock.mock_calls[0]
    assert data["client_secret"] == ISSUED_SECRET
    assert (headers or {}).get("Authorization") is None


@pytest.mark.parametrize(
    ("status", "exc", "error"),
    [
        (400, None, OAuth2TokenRequestReauthError),
        (200, ClientError(), OAuth2TokenRequestConnectionError),
    ],
)
async def test_basic_auth_maps_token_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    status: int,
    exc: Exception | None,
    error: type[Exception],
) -> None:
    """Token HTTP failures become the shared OAuth token errors."""
    aioclient_mock.post(OAUTH_TOKEN_URL, status=status, exc=exc)
    implementation = _implementation(hass, "client_secret_basic", ISSUED_SECRET)
    with pytest.raises(error):
        await implementation.async_resolve_external_data(
            {"code": "abcd", "state": {"redirect_uri": REDIRECT_URI}}
        )


async def test_manual_client_uses_the_local_implementation(
    hass: HomeAssistant,
) -> None:
    """A client id without the registration prefix keeps the previous behavior."""
    server = AuthorizationServer(OAUTH_AUTHORIZE_URL, OAUTH_TOKEN_URL)
    with authorization_server_context(server):
        implementation = await async_get_auth_implementation(
            hass, "manual-domain", ClientCredential("manual-client", "secret")
        )
    assert isinstance(implementation, AuthImplementation)


async def test_registered_client_matches_the_authorization_server(
    hass: HomeAssistant,
) -> None:
    """A registered client is used only with the server that issued it."""
    encoded = _encoded_client()
    server = AuthorizationServer(OAUTH_AUTHORIZE_URL, OAUTH_TOKEN_URL)
    with authorization_server_context(server):
        implementation = await async_get_auth_implementation(
            hass,
            "auth-domain",
            ClientCredential(encoded, ISSUED_SECRET, DCR_CLIENT_NAME),
        )
    assert isinstance(implementation, McpRegisteredOAuth2Implementation)
    assert implementation.client_id == ISSUED_CLIENT_ID
    assert implementation.client_secret == ""


async def test_registered_client_for_another_server_is_not_applicable(
    hass: HomeAssistant,
) -> None:
    """A client issued for one server is not offered to another."""
    encoded = _encoded_client(
        "https://other.example/authorize", "https://other.example/token"
    )
    server = AuthorizationServer(OAUTH_AUTHORIZE_URL, OAUTH_TOKEN_URL)
    with (
        authorization_server_context(server),
        pytest.raises(AuthImplementationNotApplicable),
    ):
        await async_get_auth_implementation(
            hass, "auth-domain", ClientCredential(encoded, "")
        )


@respx.mock
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_dynamic_registration_creates_an_entry(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Register at the advertised endpoint and finish the OAuth flow."""
    caplog.set_level(logging.DEBUG)
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    respx.post(REGISTRATION_ENDPOINT).mock(
        return_value=httpx2.Response(201, json={"client_id": ISSUED_CLIENT_ID})
    )
    result = await _run_user_flow(
        hass,
        mock_mcp_client,
        _server_metadata(
            registration_endpoint=REGISTRATION_ENDPOINT,
            token_endpoint_auth_methods_supported=["none"],
        ),
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    query = URL(result["url"]).query
    assert query["client_id"] == ISSUED_CLIENT_ID
    assert query["code_challenge_method"] == "S256"
    assert query["code_challenge"]
    state = config_entry_oauth2_flow._encode_jwt(
        hass, {"flow_id": result["flow_id"], "redirect_uri": REDIRECT_URI}
    )
    client = await hass_client_no_auth()
    response = await client.get(f"{CALLBACK_PATH}?code=abcd&state={state}")
    assert response.status == 200

    aioclient_mock.post(OAUTH_TOKEN_URL, json=OAUTH_TOKEN_PAYLOAD)
    mock_mcp_client.side_effect = None
    initialized = Mock()
    initialized.serverInfo.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = initialized
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_API_NAME

    _method, _url, data, _headers = aioclient_mock.mock_calls[0]
    assert data["client_id"] == ISSUED_CLIENT_ID
    assert "client_secret" not in data
    assert "code_verifier" in data

    credentials = hass.data[DATA_COMPONENT].async_client_credentials(DOMAIN)
    assert len(credentials) == 1
    auth_domain, credential = next(iter(credentials.items()))
    assert decode_registered_client_id(credential.client_id) == (
        OAUTH_AUTHORIZE_URL,
        OAUTH_TOKEN_URL,
        ISSUED_CLIENT_ID,
        "none",
    )
    assert credential.client_secret == ""
    assert result["data"]["auth_implementation"] == auth_domain
    assert auth_domain == registered_client_auth_domain(credential.client_id)
    result["data"].pop(CONF_TOKEN)
    assert ISSUED_SECRET not in caplog.text


@respx.mock
@pytest.mark.usefixtures("current_request_with_host")
async def test_relative_registration_endpoint(
    hass: HomeAssistant, mock_mcp_client: Mock, caplog: pytest.LogCaptureFixture
) -> None:
    """Join a relative endpoint to the authorization server and default to basic."""
    caplog.set_level(logging.DEBUG)
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    route = respx.post("http://1.1.1.1:8080/register").mock(
        return_value=httpx2.Response(
            201,
            json={"client_id": ISSUED_CLIENT_ID, "client_secret": ISSUED_SECRET},
        )
    )
    result = await _run_user_flow(
        hass,
        mock_mcp_client,
        _server_metadata(registration_endpoint="/register"),
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert URL(result["url"]).query["client_id"] == ISSUED_CLIENT_ID
    body = json.loads(route.calls.last.request.content)
    assert body["token_endpoint_auth_method"] == "client_secret_basic"
    assert ISSUED_SECRET not in caplog.text


@pytest.mark.parametrize("endpoint", [None, "", 5])
@respx.mock
async def test_missing_registration_endpoint_asks_for_credentials(
    hass: HomeAssistant, mock_mcp_client: Mock, endpoint: Any
) -> None:
    """Without an advertised endpoint, registration is not attempted."""
    result = await _run_user_flow(
        hass,
        mock_mcp_client,
        _server_metadata(registration_endpoint=endpoint),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_credentials"
    assert "POST" not in [call.request.method for call in respx.calls]


@pytest.mark.parametrize(
    "methods",
    [[], "client_secret_basic", ["private_key_jwt"], None, [1]],
)
@respx.mock
@pytest.mark.usefixtures("current_request_with_host")
async def test_unsupported_auth_methods_do_not_register(
    hass: HomeAssistant, mock_mcp_client: Mock, methods: Any
) -> None:
    """An unusable auth-method advertisement aborts before a client is created."""
    result = await _run_user_flow(
        hass,
        mock_mcp_client,
        _server_metadata(
            registration_endpoint=REGISTRATION_ENDPOINT,
            token_endpoint_auth_methods_supported=methods,
        ),
    )
    assert result["reason"] == "oauth_registration_failed"
    assert "POST" not in [call.request.method for call in respx.calls]


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (httpx2.TimeoutException("slow"), "timeout_connect"),
        (httpx2.ConnectError("down"), "cannot_connect"),
    ],
)
@respx.mock
@pytest.mark.usefixtures("current_request_with_host")
async def test_registration_transport_errors(
    hass: HomeAssistant, mock_mcp_client: Mock, error: Exception, reason: str
) -> None:
    """Network errors while registering use the existing connection aborts."""
    respx.post(REGISTRATION_ENDPOINT).mock(side_effect=error)
    result = await _run_user_flow(
        hass,
        mock_mcp_client,
        _server_metadata(
            registration_endpoint=REGISTRATION_ENDPOINT,
            token_endpoint_auth_methods_supported=["none"],
        ),
    )
    assert result["reason"] == reason


@respx.mock
async def test_registration_without_a_redirect_host(
    hass: HomeAssistant, mock_mcp_client: Mock
) -> None:
    """Abort when Home Assistant has no URL for the OAuth callback."""
    result = await _run_user_flow(
        hass,
        mock_mcp_client,
        _server_metadata(
            registration_endpoint=REGISTRATION_ENDPOINT,
            token_endpoint_auth_methods_supported=["none"],
        ),
    )
    assert result["reason"] == "no_url_available"
    assert result["description_placeholders"]["docs_url"] == (
        "https://www.home-assistant.io/more-info/no-url-available"
    )
    assert "POST" not in [call.request.method for call in respx.calls]


@respx.mock
async def test_registration_rejects_an_invalid_redirect_uri(
    hass: HomeAssistant, mock_mcp_client: Mock
) -> None:
    """Abort when the callback URI cannot be sent as client metadata."""
    with patch(
        "homeassistant.components.mcp.config_flow.async_get_redirect_uri",
        return_value="not a url",
    ):
        result = await _run_user_flow(
            hass,
            mock_mcp_client,
            _server_metadata(
                registration_endpoint=REGISTRATION_ENDPOINT,
                token_endpoint_auth_methods_supported=["none"],
            ),
        )
    assert result["reason"] == "oauth_registration_failed"
    assert "POST" not in [call.request.method for call in respx.calls]


@respx.mock
@pytest.mark.usefixtures("current_request_with_host")
async def test_registration_aborts_when_the_client_is_not_offered(
    hass: HomeAssistant, mock_mcp_client: Mock
) -> None:
    """Abort when the stored client is not available for this server."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    respx.post(REGISTRATION_ENDPOINT).mock(
        return_value=httpx2.Response(201, json={"client_id": ISSUED_CLIENT_ID})
    )
    with patch(
        "homeassistant.components.mcp.config_flow.async_get_implementations",
        return_value={},
    ):
        result = await _run_user_flow(
            hass,
            mock_mcp_client,
            _server_metadata(
                registration_endpoint=REGISTRATION_ENDPOINT,
                token_endpoint_auth_methods_supported=["none"],
            ),
        )
    assert result["reason"] == "oauth_registration_failed"


@respx.mock
async def test_foreign_registered_client_is_not_offered(
    hass: HomeAssistant, mock_mcp_client: Mock
) -> None:
    """A client for another authorization server does not skip manual setup."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    encoded = _encoded_client(
        "https://other.example/authorize", "https://other.example/token"
    )
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(encoded, ""),
        registered_client_auth_domain(encoded),
    )
    result = await _run_user_flow(hass, mock_mcp_client, _server_metadata())
    assert result["reason"] == "missing_credentials"


@respx.mock
async def test_matching_registered_client_is_offered(
    hass: HomeAssistant, mock_mcp_client: Mock
) -> None:
    """A client for this authorization server can be selected."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    encoded = _encoded_client()
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(encoded, "", DCR_CLIENT_NAME),
        registered_client_auth_domain(encoded),
    )
    result = await _run_user_flow(hass, mock_mcp_client, _server_metadata())
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "credentials_choice"
