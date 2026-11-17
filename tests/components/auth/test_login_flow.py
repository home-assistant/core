"""Tests for the login flow."""

import asyncio
from http import HTTPStatus
from typing import Any
from unittest.mock import patch

from aiohttp import ClientResponse, web
from aiohttp.test_utils import TestClient
import pytest
from pytest_homeassistant.common import CLIENT_ID, CLIENT_REDIRECT_URI
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.auth import AuthManagerFlowManager
from homeassistant.components.auth import indieauth
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.setup import async_setup_component

from . import BASE_CONFIG, async_setup_auth

_TRUSTED_NETWORKS_CONFIG = {
    "type": "trusted_networks",
    "trusted_networks": ["192.168.0.1"],
    "trusted_users": {
        "192.168.0.1": [
            "a1ab982744b64757bf80515589258924",
            {"group": "system-group"},
        ]
    },
}


@pytest.mark.parametrize(
    ("ip", "preselect_remember_me"),
    [
        ("192.168.1.10", True),
        ("::ffff:192.168.0.10", True),
        ("1.2.3.4", False),
        ("2001:db8::1", False),
    ],
)
@pytest.mark.parametrize(
    ("provider_configs", "expected"),
    [
        (
            BASE_CONFIG,
            [{"name": "Example", "type": "insecure_example", "id": None}],
        ),
        (
            [{"type": "homeassistant"}],
            [
                {
                    "name": "Home Assistant Local",
                    "type": "homeassistant",
                    "id": None,
                }
            ],
        ),
    ],
)
async def test_fetch_auth_providers(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    provider_configs: list[dict[str, Any]],
    expected: list[dict[str, Any]],
    ip: str,
    preselect_remember_me: bool,
) -> None:
    """Test fetching auth providers."""
    client = await async_setup_auth(
        hass, aiohttp_client, provider_configs, custom_ip=ip
    )
    resp = await client.get("/auth/providers")
    assert resp.status == HTTPStatus.OK
    assert await resp.json() == {
        "providers": expected,
        "preselect_remember_me": preselect_remember_me,
    }


@pytest.mark.parametrize(
    ("ip", "expected"),
    [
        (
            "192.168.0.1",
            [{"name": "Trusted Networks", "type": "trusted_networks", "id": None}],
        ),
        ("::ffff:192.168.0.10", []),
        ("1.2.3.4", []),
        ("2001:db8::1", []),
    ],
)
async def test_fetch_auth_providers_trusted_network(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    expected: list[dict[str, Any]],
    ip: str,
) -> None:
    """Test fetching auth providers."""
    client = await async_setup_auth(
        hass, aiohttp_client, [_TRUSTED_NETWORKS_CONFIG], custom_ip=ip
    )
    resp = await client.get("/auth/providers")
    assert resp.status == HTTPStatus.OK
    assert (await resp.json())["providers"] == expected


async def test_fetch_auth_providers_skips_providers_that_cannot_start_login(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test a provider that cannot be used right now is left off the list."""
    client = await async_setup_auth(hass, aiohttp_client, BASE_CONFIG)
    with patch(
        "homeassistant.auth.providers.insecure_example.ExampleAuthProvider"
        ".async_can_start_login",
        return_value=False,
    ):
        resp = await client.get("/auth/providers")

    assert resp.status == HTTPStatus.OK
    assert (await resp.json())["providers"] == []


async def test_login_flow_refuses_providers_that_cannot_start_login(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test a provider left off the login screen can't be started directly."""
    client = await async_setup_auth(hass, aiohttp_client, BASE_CONFIG)
    with patch(
        "homeassistant.auth.providers.insecure_example.ExampleAuthProvider"
        ".async_can_start_login",
        return_value=False,
    ):
        resp = await client.post(
            "/auth/login_flow",
            json={
                "client_id": CLIENT_ID,
                "handler": ["insecure_example", None],
                "redirect_uri": CLIENT_REDIRECT_URI,
            },
        )

    assert resp.status == HTTPStatus.NOT_FOUND
    assert await resp.json() == {"message": "Invalid handler specified"}


async def test_login_flow_trusted_networks_from_trusted_network(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test a trusted networks login can be started from a trusted network."""
    client = await async_setup_auth(
        hass, aiohttp_client, [_TRUSTED_NETWORKS_CONFIG], custom_ip="192.168.0.1"
    )
    resp = await client.post(
        "/auth/login_flow",
        json={
            "client_id": CLIENT_ID,
            "handler": ["trusted_networks", None],
            "redirect_uri": CLIENT_REDIRECT_URI,
        },
    )

    assert resp.status == HTTPStatus.OK


@pytest.mark.parametrize(
    "provider_configs",
    [
        pytest.param([_TRUSTED_NETWORKS_CONFIG], id="untrusted-network"),
        pytest.param(BASE_CONFIG, id="not-configured"),
    ],
)
async def test_login_flow_hides_unavailable_trusted_networks(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    provider_configs: list[dict[str, Any]],
) -> None:
    """Test trusted networks from outside is answered like it isn't configured."""
    client = await async_setup_auth(
        hass, aiohttp_client, provider_configs, custom_ip="1.2.3.4"
    )
    resp = await client.post(
        "/auth/login_flow",
        json={
            "client_id": CLIENT_ID,
            "handler": ["trusted_networks", None],
            "redirect_uri": CLIENT_REDIRECT_URI,
        },
    )

    assert resp.status == HTTPStatus.NOT_FOUND
    assert await resp.json() == {"message": "Invalid handler specified"}


async def test_fetch_auth_providers_onboarding(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test fetching auth providers."""
    client = await async_setup_auth(hass, aiohttp_client)
    with patch(
        "homeassistant.components.onboarding.async_is_user_onboarded",
        return_value=False,
    ):
        resp = await client.get("/auth/providers")
    assert resp.status == HTTPStatus.BAD_REQUEST
    assert await resp.json() == {
        "message": "Onboarding not finished",
        "code": "onboarding_required",
    }


async def test_cannot_get_flows_in_progress(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test we cannot get flows in progress."""
    client = await async_setup_auth(hass, aiohttp_client, [])
    resp = await client.get("/auth/login_flow")
    assert resp.status == HTTPStatus.METHOD_NOT_ALLOWED


async def test_invalid_username_password(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test we cannot get flows in progress."""
    client = await async_setup_auth(hass, aiohttp_client)
    resp = await client.post(
        "/auth/login_flow",
        json={
            "client_id": CLIENT_ID,
            "handler": ["insecure_example", None],
            "redirect_uri": CLIENT_REDIRECT_URI,
        },
    )
    assert resp.status == HTTPStatus.OK
    step = await resp.json()

    # Incorrect username
    with patch(
        "homeassistant.components.auth.login_flow.process_wrong_login"
    ) as mock_process_wrong_login:
        resp = await client.post(
            f"/auth/login_flow/{step['flow_id']}",
            json={
                "client_id": CLIENT_ID,
                "username": "wrong-user",
                "password": "test-pass",
            },
        )

    assert resp.status == HTTPStatus.OK
    step = await resp.json()
    assert len(mock_process_wrong_login.mock_calls) == 1

    assert step["step_id"] == "init"
    assert step["errors"]["base"] == "invalid_auth"

    # Incorrect password
    with patch(
        "homeassistant.components.auth.login_flow.process_wrong_login"
    ) as mock_process_wrong_login:
        resp = await client.post(
            f"/auth/login_flow/{step['flow_id']}",
            json={
                "client_id": CLIENT_ID,
                "username": "test-user",
                "password": "wrong-pass",
            },
        )

    assert resp.status == HTTPStatus.OK
    step = await resp.json()
    assert len(mock_process_wrong_login.mock_calls) == 1

    assert step["step_id"] == "init"
    assert step["errors"]["base"] == "invalid_auth"

    # Incorrect username and invalid redirect URI fails on wrong login
    with patch(
        "homeassistant.components.auth.login_flow.process_wrong_login"
    ) as mock_process_wrong_login:
        resp = await client.post(
            f"/auth/login_flow/{step['flow_id']}",
            json={
                "client_id": CLIENT_ID,
                "username": "wrong-user",
                "password": "test-pass",
            },
        )

    assert resp.status == HTTPStatus.OK
    step = await resp.json()
    assert len(mock_process_wrong_login.mock_calls) == 1

    assert step["step_id"] == "init"
    assert step["errors"]["base"] == "invalid_auth"


async def test_invalid_redirect_uri(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test invalid redirect URI."""
    client = await async_setup_auth(hass, aiohttp_client)
    resp = await client.post(
        "/auth/login_flow",
        json={
            "client_id": CLIENT_ID,
            "handler": ["insecure_example", None],
            "redirect_uri": "https://some-other-domain.com",
        },
    )
    assert resp.status == HTTPStatus.OK
    step = await resp.json()

    with (
        patch(
            "homeassistant.components.auth.indieauth.fetch_redirect_uris",
            return_value=[],
        ),
        patch(
            "homeassistant.components.http.ban.process_wrong_login"
        ) as mock_process_wrong_login,
    ):
        resp = await client.post(
            f"/auth/login_flow/{step['flow_id']}",
            json={
                "client_id": CLIENT_ID,
                "username": "test-user",
                "password": "test-pass",
            },
        )

    assert resp.status == HTTPStatus.FORBIDDEN
    data = await resp.json()
    assert len(mock_process_wrong_login.mock_calls) == 1

    assert data["message"] == "Invalid redirect URI"


@pytest.mark.parametrize(
    "authorization_data",
    [{}, {"response_type": "code"}],
)
async def test_login_exist_user(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    authorization_data: dict[str, str],
) -> None:
    """Test logging in with exist user."""
    client = await async_setup_auth(hass, aiohttp_client, setup_api=True)
    cred = await hass.auth.auth_providers[0].async_get_or_create_credentials(
        {"username": "test-user"}
    )
    await hass.auth.async_get_or_create_user(cred)

    resp = await client.post(
        "/auth/login_flow",
        json={
            "client_id": CLIENT_ID,
            "handler": ["insecure_example", None],
            "redirect_uri": CLIENT_REDIRECT_URI,
            **authorization_data,
        },
    )
    assert resp.status == HTTPStatus.OK
    step = await resp.json()

    with patch(
        "homeassistant.components.auth.login_flow.process_success_login"
    ) as mock_process_success_login:
        resp = await client.post(
            f"/auth/login_flow/{step['flow_id']}",
            json={
                "client_id": CLIENT_ID,
                "username": "test-user",
                "password": "test-pass",
            },
        )

    assert resp.status == HTTPStatus.OK
    step = await resp.json()
    assert step["type"] == "create_entry"
    assert len(step["result"]) > 1
    assert len(mock_process_success_login.mock_calls) == 1


async def test_login_local_only_user(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test logging in with local only user."""
    client = await async_setup_auth(hass, aiohttp_client, setup_api=True)
    cred = await hass.auth.auth_providers[0].async_get_or_create_credentials(
        {"username": "test-user"}
    )
    user = await hass.auth.async_get_or_create_user(cred)
    await hass.auth.async_update_user(user, local_only=True)

    resp = await client.post(
        "/auth/login_flow",
        json={
            "client_id": CLIENT_ID,
            "handler": ["insecure_example", None],
            "redirect_uri": CLIENT_REDIRECT_URI,
        },
    )
    assert resp.status == HTTPStatus.OK
    step = await resp.json()

    with patch(
        "homeassistant.components.auth.login_flow.async_user_not_allowed_do_auth",
        return_value="User is local only",
    ) as mock_not_allowed_do_auth:
        resp = await client.post(
            f"/auth/login_flow/{step['flow_id']}",
            json={
                "client_id": CLIENT_ID,
                "username": "test-user",
                "password": "test-pass",
            },
        )

    assert resp.status == HTTPStatus.FORBIDDEN
    assert len(mock_not_allowed_do_auth.mock_calls) == 1
    assert await resp.json() == {"message": "Login blocked: User is local only"}


async def test_login_exist_user_ip_changes(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test logging in and the ip address changes results in an rejection."""
    client = await async_setup_auth(hass, aiohttp_client, setup_api=True)
    cred = await hass.auth.auth_providers[0].async_get_or_create_credentials(
        {"username": "test-user"}
    )
    await hass.auth.async_get_or_create_user(cred)

    resp = await client.post(
        "/auth/login_flow",
        json={
            "client_id": CLIENT_ID,
            "handler": ["insecure_example", None],
            "redirect_uri": CLIENT_REDIRECT_URI,
        },
    )
    assert resp.status == 200
    step = await resp.json()

    #
    # Here we modify the ip_address in the context to make sure
    # when ip address changes in the middle of the login flow we prevent logins.
    #
    # This method was chosen because it seemed less likely to break
    # vs patching aiohttp internals to fake the ip address
    #
    for flow_id, flow in hass.auth.login_flow._progress.items():
        assert flow_id == step["flow_id"]
        flow.context["ip_address"] = "10.2.3.1"

    resp = await client.post(
        f"/auth/login_flow/{step['flow_id']}",
        json={
            "client_id": CLIENT_ID,
            "redirect_uri": CLIENT_REDIRECT_URI,
            "username": "test-user",
            "password": "test-pass",
        },
    )

    assert resp.status == 400
    response = await resp.json()
    assert response == {"message": "IP address changed"}


async def _async_post_while_held(
    client: TestClient,
    flow_id: str,
    body: dict[str, str],
    held: asyncio.Event,
    release: asyncio.Event,
) -> tuple[ClientResponse, ClientResponse]:
    """Post to a flow twice, the second time while the first request is held."""
    first = asyncio.create_task(client.post(f"/auth/login_flow/{flow_id}", json=body))
    await held.wait()
    second = await client.post(f"/auth/login_flow/{flow_id}", json=body)
    release.set()
    return await first, second


@pytest.mark.parametrize(
    ("owner", "held_name"),
    [
        pytest.param(AuthManagerFlowManager, "async_configure", id="running-step"),
        # A finished flow is gone while its response is built.
        pytest.param(indieauth, "verify_redirect_uri", id="building-response"),
    ],
)
async def test_concurrent_requests_cannot_advance_the_same_flow(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    owner: object,
    held_name: str,
) -> None:
    """Test a second request gets a conflict rather than racing the first one."""
    client = await async_setup_auth(hass, aiohttp_client)
    resp = await client.post(
        "/auth/login_flow",
        json={
            "client_id": CLIENT_ID,
            "handler": ["insecure_example", None],
            "redirect_uri": CLIENT_REDIRECT_URI,
        },
    )
    flow_id = (await resp.json())["flow_id"]

    held = asyncio.Event()
    release = asyncio.Event()
    original = getattr(owner, held_name)

    async def held_call(*args: Any, **kwargs: Any) -> Any:
        held.set()
        await release.wait()
        return await original(*args, **kwargs)

    with (
        patch.object(owner, held_name, held_call),
        patch(
            "homeassistant.components.http.ban.process_wrong_login"
        ) as mock_process_wrong_login,
    ):
        first, second = await _async_post_while_held(
            client,
            flow_id,
            {"client_id": CLIENT_ID, "username": "test-user", "password": "test-pass"},
            held,
            release,
        )

    assert second.status == HTTPStatus.CONFLICT
    assert await second.json() == {"message": "Flow request already in progress"}
    assert first.status == HTTPStatus.OK
    assert (await first.json())["type"] == "create_entry"
    # A busy flow is not a failed login, so the client is not banned for it.
    mock_process_wrong_login.assert_not_called()


@pytest.mark.parametrize(
    ("first_input", "first_status"),
    [
        pytest.param(
            {"username": "test-user", "password": "wrong-pass"},
            HTTPStatus.OK,
            id="invalid-password",
        ),
        # The step's schema rejects it, so async_configure raises.
        pytest.param({"username": "test-user"}, HTTPStatus.BAD_REQUEST, id="raised"),
    ],
)
async def test_flow_can_be_continued_after_a_request(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    first_input: dict[str, str],
    first_status: HTTPStatus,
) -> None:
    """Test a flow is no longer busy once a request has finished."""
    client = await async_setup_auth(hass, aiohttp_client)
    resp = await client.post(
        "/auth/login_flow",
        json={
            "client_id": CLIENT_ID,
            "handler": ["insecure_example", None],
            "redirect_uri": CLIENT_REDIRECT_URI,
        },
    )
    flow_id = (await resp.json())["flow_id"]

    resp = await client.post(
        f"/auth/login_flow/{flow_id}", json={"client_id": CLIENT_ID, **first_input}
    )
    assert resp.status == first_status

    resp = await client.post(
        f"/auth/login_flow/{flow_id}",
        json={"client_id": CLIENT_ID, "username": "test-user", "password": "test-pass"},
    )
    assert resp.status == HTTPStatus.OK
    assert (await resp.json())["type"] == "create_entry"


@pytest.mark.parametrize(
    ("counted_by", "login_input", "first_status"),
    [
        pytest.param(
            "homeassistant.components.auth.login_flow.process_wrong_login",
            {"username": "test-user", "password": "wrong-pass"},
            HTTPStatus.OK,
            id="invalid-password",
        ),
        pytest.param(
            "homeassistant.components.http.ban.process_wrong_login",
            {"username": "test-user"},
            HTTPStatus.BAD_REQUEST,
            id="malformed-input",
        ),
    ],
)
async def test_flow_stays_busy_until_a_failed_login_is_processed(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    counted_by: str,
    login_input: dict[str, str],
    first_status: HTTPStatus,
) -> None:
    """Test the next attempt waits until the previous failure has been counted."""
    client = await async_setup_auth(hass, aiohttp_client)
    resp = await client.post(
        "/auth/login_flow",
        json={
            "client_id": CLIENT_ID,
            "handler": ["insecure_example", None],
            "redirect_uri": CLIENT_REDIRECT_URI,
        },
    )
    flow_id = (await resp.json())["flow_id"]

    held = asyncio.Event()
    release = asyncio.Event()

    async def held_process_wrong_login(_request: web.Request) -> None:
        held.set()
        await release.wait()

    with patch(counted_by, held_process_wrong_login):
        first, second = await _async_post_while_held(
            client, flow_id, {"client_id": CLIENT_ID, **login_input}, held, release
        )

    assert second.status == HTTPStatus.CONFLICT
    assert first.status == first_status


@pytest.mark.usefixtures("current_request_with_host")  # Has example.com host
@pytest.mark.parametrize(
    ("config", "expected_url_prefix", "extra_response_data"),
    [
        (
            {
                "internal_url": "http://192.168.1.100:8123",
                # Current request matches external url
                "external_url": "https://example.com",
            },
            "https://example.com",
            {"issuer": "https://example.com"},
        ),
        (
            {
                # Current request matches internal url
                "internal_url": "https://example.com",
                "external_url": "https://other.com",
            },
            "https://example.com",
            {"issuer": "https://example.com"},
        ),
        (
            {
                # Current request does not match either url
                "internal_url": "https://other.com",
                "external_url": "https://again.com",
            },
            "",
            {},
        ),
    ],
    ids=["external_url", "internal_url", "no_match"],
)
async def test_well_known_auth_info(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    config: dict[str, str],
    expected_url_prefix: str,
    extra_response_data: dict[str, str],
) -> None:
    """Test well-known OAuth endpoint with different URL configurations."""
    await async_process_ha_core_config(hass, config)
    client = await async_setup_auth(hass, aiohttp_client, setup_api=True)
    resp = await client.get(
        "/.well-known/oauth-authorization-server",
    )
    assert resp.status == 200
    assert await resp.json() == {
        **extra_response_data,
        "authorization_endpoint": f"{expected_url_prefix}/auth/authorize",
        "token_endpoint": f"{expected_url_prefix}/auth/token",
        "revocation_endpoint": f"{expected_url_prefix}/auth/revoke",
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": ["none"],
        "revocation_endpoint_auth_methods_supported": ["none"],
        "client_id_metadata_document_supported": True,
        "code_challenge_methods_supported": ["S256"],
        "response_types_supported": ["code"],
        "service_documentation": "https://contributors.home-assistant.io/core/internals/auth-api/",
    }


@pytest.mark.usefixtures("current_request_with_host")  # Has example.com host
@pytest.mark.parametrize(
    ("config", "expected_response"),
    [
        (
            {
                "internal_url": "http://192.168.1.100:8123",
                # Current request matches external url
                "external_url": "https://example.com",
            },
            {
                "resource": "https://example.com",
                "authorization_servers": ["https://example.com"],
                "resource_documentation": "https://contributors.home-assistant.io/core/internals/auth-api/",
            },
        ),
        (
            {
                # Current request matches internal url
                "internal_url": "https://example.com",
                "external_url": "https://other.com",
            },
            {
                "resource": "https://example.com",
                "authorization_servers": ["https://example.com"],
                "resource_documentation": "https://contributors.home-assistant.io/core/internals/auth-api/",
            },
        ),
    ],
    ids=["external_url", "internal_url"],
)
async def test_well_known_protected_resource(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    config: dict[str, str],
    expected_response: dict[str, Any],
) -> None:
    """Test the well-known OAuth protected resource metadata endpoint per RFC9728."""
    await async_process_ha_core_config(hass, config)
    client = await async_setup_auth(hass, aiohttp_client, setup_api=True)
    resp = await client.get(
        "/.well-known/oauth-protected-resource",
    )
    assert resp.status == 200
    assert await resp.json() == expected_response


@pytest.mark.usefixtures("current_request_with_host")  # Has example.com host
async def test_well_known_protected_resource_no_url(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
) -> None:
    """Test the protected resource metadata returns 404 when no URL is configured."""
    await async_process_ha_core_config(
        hass,
        {
            "internal_url": "https://other.com",
            "external_url": "https://again.com",
        },
    )
    client = await async_setup_auth(hass, aiohttp_client, setup_api=True)
    resp = await client.get(
        "/.well-known/oauth-protected-resource",
    )
    assert resp.status == 404


@pytest.mark.parametrize(
    ("payload", "expected_message"),
    [
        (
            {
                "code_challenge_method": "S256",
            },
            "code_challenge required when code_challenge_method is provided",
        ),
        (
            {
                "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
            },
            "Transform algorithm not supported",
        ),
        (
            {
                "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
                "code_challenge_method": "plain",
            },
            "Transform algorithm not supported",
        ),
        (
            {
                "code_challenge": "short",
                "code_challenge_method": "S256",
            },
            "Message format incorrect",
        ),
        (
            {
                "code_challenge": "a" * 43 + "=",
                "code_challenge_method": "S256",
            },
            "Message format incorrect",
        ),
        (
            {
                "response_type": "token",
            },
            "Response type not supported",
        ),
    ],
    ids=[
        "method_without_challenge",
        "challenge_without_method",
        "unsupported_plain_method",
        "challenge_too_short",
        "challenge_padded",
        "unsupported_response_type",
    ],
)
async def test_login_flow_pkce_validation(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    payload: dict[str, str],
    expected_message: str,
) -> None:
    """Test PKCE parameter validation in login_flow."""
    client = await async_setup_auth(hass, aiohttp_client, setup_api=True)
    resp = await client.post(
        "/auth/login_flow",
        json={
            "client_id": CLIENT_ID,
            "handler": ["insecure_example", None],
            "redirect_uri": CLIENT_REDIRECT_URI,
            **payload,
        },
    )
    assert resp.status == HTTPStatus.BAD_REQUEST
    result = await resp.json()
    assert expected_message in result["message"]


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"client_id": CLIENT_ID + "?" + "x" * 2048}, id="client_id"),
        pytest.param(
            {"redirect_uri": CLIENT_REDIRECT_URI + "?" + "x" * 2048},
            id="redirect_uri",
        ),
    ],
)
async def test_login_flow_url_too_long(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    payload: dict[str, str],
) -> None:
    """Test login flows reject overly long URLs."""
    client = await async_setup_auth(hass, aiohttp_client)
    resp = await client.post(
        "/auth/login_flow",
        json={
            "client_id": CLIENT_ID,
            "handler": ["insecure_example", None],
            "redirect_uri": CLIENT_REDIRECT_URI,
            **payload,
        },
    )
    assert resp.status == HTTPStatus.BAD_REQUEST
    assert not hass.auth.login_flow.async_progress()


@pytest.mark.parametrize(
    "path",
    [
        pytest.param(
            "/.well-known/oauth-authorization-server", id="authorization-server"
        ),
        pytest.param("/.well-known/oauth-protected-resource", id="protected-resource"),
    ],
)
async def test_well_known_auth_info_allows_cors(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator, path: str
) -> None:
    """Test browser clients can discover authorization server capabilities."""
    client = await async_setup_auth(hass, aiohttp_client, setup_api=True)

    resp = await client.get(
        path,
        headers={"origin": "https://client.example"},
    )

    assert resp.status == HTTPStatus.OK
    assert resp.headers["Access-Control-Allow-Origin"] == "https://client.example"


@pytest.mark.parametrize(
    ("http_config", "headers"),
    [
        pytest.param({}, {"Host": "[2001:db8::1]"}, id="direct"),
        pytest.param(
            {"use_x_forwarded_for": True, "trusted_proxies": ["127.0.0.1"]},
            {
                "X-Forwarded-For": "2001:db8::10",
                "X-Forwarded-Host": "[2001:db8::1]",
                "X-Forwarded-Proto": "http",
            },
            id="trusted-proxy",
        ),
    ],
)
async def test_login_client_id_matches_request_origin(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    http_config: dict[str, Any],
    headers: dict[str, str],
) -> None:
    """Test logging in with a public IP client_id that matches the request origin."""
    assert await async_setup_component(hass, "http", {"http": http_config})
    client = await async_setup_auth(hass, aiohttp_client)
    client_id = "http://[2001:db8::1]/"

    resp = await client.post(
        "/auth/login_flow",
        json={
            "client_id": client_id,
            "handler": ["insecure_example", None],
            "redirect_uri": "http://[2001:db8::1]/?auth_callback=1",
        },
        headers=headers,
    )
    assert resp.status == HTTPStatus.OK
    step = await resp.json()

    resp = await client.post(
        f"/auth/login_flow/{step['flow_id']}",
        json={
            "client_id": client_id,
            "username": "test-user",
            "password": "test-pass",
        },
        headers=headers,
    )
    assert resp.status == HTTPStatus.OK
    step = await resp.json()
    assert step["type"] == "create_entry"

    resp = await client.post(
        "/auth/token",
        data={
            "client_id": client_id,
            "grant_type": "authorization_code",
            "code": step["result"],
        },
        headers=headers,
    )
    assert resp.status == HTTPStatus.OK
    tokens = await resp.json()
    assert "access_token" in tokens

    resp = await client.post(
        "/auth/token",
        data={
            "client_id": client_id,
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
        },
        headers=headers,
    )
    assert resp.status == HTTPStatus.OK


async def test_login_client_id_does_not_match_request_origin(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test a public IP client_id is rejected when the request origin differs."""
    client = await async_setup_auth(hass, aiohttp_client)

    resp = await client.post(
        "/auth/login_flow",
        json={
            "client_id": "http://[2001:db8::1]/",
            "handler": ["insecure_example", None],
            "redirect_uri": "http://[2001:db8::1]/?auth_callback=1",
        },
        headers={"Host": "[2001:db8::2]"},
    )
    assert resp.status == HTTPStatus.BAD_REQUEST
    assert (await resp.json())["message"] == "Invalid client id"
