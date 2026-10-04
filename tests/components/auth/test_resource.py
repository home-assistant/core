"""Test OAuth resource indicators and grant binding."""

from http import HTTPStatus
from unittest.mock import patch

import pytest

from homeassistant.auth.models import Credentials
from homeassistant.components.auth import (
    AuthorizationCodeValidationError,
    _create_auth_code_store,
)
from homeassistant.components.auth.resource import normalize_resource
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import NoURLAvailableError

from . import PKCE_AUTHORIZATION_REQUEST, async_setup_auth

from tests.common import CLIENT_ID, CLIENT_REDIRECT_URI
from tests.typing import ClientSessionGenerator

RESOURCE = "https://example.com"


@pytest.mark.parametrize(
    "resource",
    [
        pytest.param(RESOURCE, id="origin"),
        pytest.param(f"{RESOURCE}/", id="trailing-slash"),
        pytest.param("https://EXAMPLE.COM:443/", id="canonical-origin"),
    ],
)
def test_normalize_resource(hass: HomeAssistant, resource: str) -> None:
    """Equivalent origins use the same resource identifier."""
    with patch("homeassistant.components.auth.resource.get_url", return_value=RESOURCE):
        assert normalize_resource(hass, resource) == RESOURCE


def test_legacy_resource_needs_no_url(hass: HomeAssistant) -> None:
    """Legacy grants continue to work without a configured public URL."""
    with patch("homeassistant.components.auth.resource.get_url") as get_url:
        assert normalize_resource(hass, None) is None
    get_url.assert_not_called()


@pytest.mark.parametrize(
    "resource",
    [
        pytest.param("", id="empty"),
        pytest.param("https://attacker.example", id="foreign-origin"),
        pytest.param("https://example.com:8443", id="foreign-port"),
        pytest.param("http://example.com", id="insecure"),
        pytest.param("//example.com", id="relative"),
        pytest.param(f"{RESOURCE}/api/mcp", id="unsupported-path"),
        pytest.param(f"{RESOURCE}/.", id="normalized-path"),
        pytest.param(f"{RESOURCE}?", id="empty-query"),
        pytest.param(f"{RESOURCE}#", id="empty-fragment"),
        pytest.param("https://user@example.com", id="userinfo"),
        pytest.param(f" {RESOURCE}", id="leading-space"),
        pytest.param("https://exam\nple.com", id="newline"),
    ],
)
def test_reject_invalid_resource(hass: HomeAssistant, resource: str) -> None:
    """Only the advertised origin can be requested as a resource."""
    with (
        patch("homeassistant.components.auth.resource.get_url", return_value=RESOURCE),
        pytest.raises(ValueError),
    ):
        normalize_resource(hass, resource)


def test_resource_requires_trusted_url(hass: HomeAssistant) -> None:
    """Request input cannot supply an otherwise unconfigured audience."""
    with (
        patch(
            "homeassistant.components.auth.resource.get_url",
            side_effect=NoURLAvailableError,
        ),
        pytest.raises(ValueError),
    ):
        normalize_resource(hass, RESOURCE)


@pytest.mark.parametrize(
    ("bound_resource", "requested_resource"),
    [
        pytest.param(RESOURCE, None, id="missing"),
        pytest.param(RESOURCE, "https://other.example", id="changed"),
        pytest.param(None, RESOURCE, id="unexpected"),
    ],
)
def test_auth_code_resource_rejected_before_consumption(
    bound_resource: str | None, requested_resource: str | None
) -> None:
    """A mismatched resource neither redeems nor consumes an authorization code."""
    store, retrieve = _create_auth_code_store()
    credential = Credentials(
        auth_provider_type="insecure_example", auth_provider_id=None, data={}
    )
    code = store(CLIENT_ID, credential, resource=bound_resource)
    assert retrieve(
        CLIENT_ID, code, resource=requested_resource
    ) == AuthorizationCodeValidationError("invalid_target")
    assert retrieve(CLIENT_ID, code, resource=bound_resource) is credential


@pytest.mark.parametrize(
    "requested_resource",
    [
        pytest.param({}, id="omitted"),
        pytest.param({"resource": RESOURCE}, id="original"),
        pytest.param({"resource": f"{RESOURCE}/"}, id="equivalent"),
    ],
)
async def test_refresh_preserves_resource(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    requested_resource: dict[str, str],
) -> None:
    """Refreshing a grant retains its original resource restriction."""
    client = await async_setup_auth(hass, aiohttp_client)
    user = await hass.auth.async_create_user("Test User")
    token = await hass.auth.async_create_refresh_token(
        user, CLIENT_ID, resource=RESOURCE
    )
    with patch("homeassistant.components.auth.resource.get_url", return_value=RESOURCE):
        response = await client.post(
            "/auth/token",
            data={
                "grant_type": "refresh_token",
                "client_id": CLIENT_ID,
                "refresh_token": token.token,
                **requested_resource,
            },
        )
    assert response.status == HTTPStatus.OK
    tokens = await response.json()
    assert hass.auth.async_validate_access_token(tokens["access_token"]) is token
    assert token.resource == RESOURCE


@pytest.mark.parametrize(
    ("bound_resource", "requested_resource"),
    [
        pytest.param(RESOURCE, "https://other.example", id="changed"),
        pytest.param(RESOURCE, "", id="empty"),
        pytest.param(None, RESOURCE, id="unexpected"),
    ],
)
async def test_refresh_rejects_resource_change(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    bound_resource: str | None,
    requested_resource: str,
) -> None:
    """Refresh tokens cannot change their target or acquire a new resource."""
    client = await async_setup_auth(hass, aiohttp_client)
    user = await hass.auth.async_create_user("Test User")
    token = await hass.auth.async_create_refresh_token(
        user, CLIENT_ID, resource=bound_resource
    )
    with patch("homeassistant.components.auth.resource.get_url", return_value=RESOURCE):
        response = await client.post(
            "/auth/token",
            data={
                "grant_type": "refresh_token",
                "client_id": CLIENT_ID,
                "refresh_token": token.token,
                "resource": requested_resource,
            },
        )
    assert response.status == HTTPStatus.BAD_REQUEST
    assert await response.json() == {"error": "invalid_target"}
    assert token.resource == bound_resource


async def test_login_flow_binds_resource(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """The initial authorization request binds the resource into the flow."""
    client = await async_setup_auth(hass, aiohttp_client)
    with patch("homeassistant.components.auth.resource.get_url", return_value=RESOURCE):
        response = await client.post(
            "/auth/login_flow",
            json={
                "client_id": CLIENT_ID,
                "redirect_uri": CLIENT_REDIRECT_URI,
                "handler": ["insecure_example", None],
                "resource": f"{RESOURCE}/",
                **PKCE_AUTHORIZATION_REQUEST,
            },
        )
    assert response.status == HTTPStatus.OK
    step = await response.json()
    flow = hass.auth.login_flow.async_get(step["flow_id"])
    assert flow["context"]["resource"] == RESOURCE


@pytest.mark.parametrize(
    ("resource", "authorization_code_type"),
    [
        pytest.param("https://other.example", "authorize", id="foreign-resource"),
        pytest.param(RESOURCE, "link_user", id="link-user"),
    ],
)
async def test_login_flow_rejects_invalid_resource(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    resource: str,
    authorization_code_type: str,
) -> None:
    """Reject unsupported resources before starting a login flow."""
    client = await async_setup_auth(hass, aiohttp_client)
    with patch("homeassistant.components.auth.resource.get_url", return_value=RESOURCE):
        response = await client.post(
            "/auth/login_flow",
            json={
                "client_id": CLIENT_ID,
                "redirect_uri": CLIENT_REDIRECT_URI,
                "handler": ["insecure_example", None],
                "resource": resource,
                "type": authorization_code_type,
                **PKCE_AUTHORIZATION_REQUEST,
            },
        )
    assert response.status == HTTPStatus.BAD_REQUEST
    assert await response.json() == {
        "error": "invalid_target",
        "message": "Invalid resource",
    }
    assert hass.auth.login_flow.async_progress() == []
