"""Tests for Home Assistant View."""

from collections.abc import Generator
from decimal import Decimal
from http import HTTPStatus
import json
import math
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import hdrs
from aiohttp.web_exceptions import (
    HTTPBadRequest,
    HTTPInternalServerError,
    HTTPUnauthorized,
)
import pytest
import voluptuous as vol

from homeassistant.components.http import KEY_HASS
from homeassistant.components.http.request_context import current_request
from homeassistant.components.http.view import (
    HomeAssistantView,
    request_handler_factory,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceNotFound, Unauthorized
from homeassistant.helpers.network import NoURLAvailableError


@pytest.fixture
def mock_request() -> Mock:
    """Mock a request."""
    return Mock(app={KEY_HASS: Mock(is_stopping=False)}, match_info={})


@pytest.fixture
def mock_request_with_stopping() -> Mock:
    """Mock a request."""
    return Mock(app={KEY_HASS: Mock(is_stopping=True)}, match_info={})


async def test_invalid_json(caplog: pytest.LogCaptureFixture) -> None:
    """Test trying to return invalid JSON."""
    with pytest.raises(HTTPInternalServerError):
        HomeAssistantView.json({"hello": Decimal("2.0")})

    assert (
        "Unable to serialize to JSON. Bad data found at"
        " $.hello=2.0(<class 'decimal.Decimal'>" in caplog.text
    )


async def test_nan_serialized_to_null() -> None:
    """Test nan serialized to null JSON."""
    response = HomeAssistantView.json(math.nan)
    assert json.loads(response.body.decode("utf-8")) is None


async def test_handling_unauthorized(mock_request: Mock) -> None:
    """Test handling unauth exceptions."""
    with pytest.raises(HTTPUnauthorized):
        await request_handler_factory(
            mock_request.app[KEY_HASS],
            Mock(requires_auth=False),
            AsyncMock(side_effect=Unauthorized),
        )(mock_request)


async def test_handling_invalid_data(mock_request: Mock) -> None:
    """Test handling unauth exceptions."""
    with pytest.raises(HTTPBadRequest):
        await request_handler_factory(
            mock_request.app[KEY_HASS],
            Mock(requires_auth=False),
            AsyncMock(side_effect=vol.Invalid("yo")),
        )(mock_request)


async def test_handling_service_not_found(mock_request: Mock) -> None:
    """Test handling unauth exceptions."""
    with pytest.raises(HTTPInternalServerError):
        await request_handler_factory(
            mock_request.app[KEY_HASS],
            Mock(requires_auth=False),
            AsyncMock(side_effect=ServiceNotFound("test", "test")),
        )(mock_request)


async def test_not_running(mock_request_with_stopping: Mock) -> None:
    """Test we get a 503 when not running."""
    response = await request_handler_factory(
        mock_request_with_stopping.app[KEY_HASS],
        Mock(requires_auth=False),
        AsyncMock(side_effect=Unauthorized),
    )(mock_request_with_stopping)
    assert response.status == HTTPStatus.SERVICE_UNAVAILABLE


async def test_invalid_handler(mock_request: Mock) -> None:
    """Test an invalid handler."""
    with pytest.raises(TypeError):
        await request_handler_factory(
            mock_request.app[KEY_HASS],
            Mock(requires_auth=False),
            AsyncMock(return_value=["not valid"]),
        )(mock_request)


async def test_requires_auth_includes_www_authenticate(
    mock_request: Mock,
) -> None:
    """Test that 401 responses include WWW-Authenticate header per RFC9728."""
    mock_request.get = Mock(return_value=False)
    with (
        patch(
            "homeassistant.helpers.network.get_url",
            return_value="https://example.com",
        ),
        pytest.raises(HTTPUnauthorized) as exc_info,
    ):
        await request_handler_factory(
            mock_request.app[KEY_HASS],
            Mock(requires_auth=True),
            AsyncMock(),
        )(mock_request)
    assert exc_info.value.headers["WWW-Authenticate"] == (
        "Bearer resource_metadata="
        '"https://example.com/.well-known/oauth-protected-resource"'
    )


async def test_requires_auth_omits_www_authenticate_without_url(
    mock_request: Mock,
) -> None:
    """Test 401 responses omit WWW-Authenticate when no URL configured."""
    mock_request.get = Mock(return_value=False)
    with (
        patch(
            "homeassistant.helpers.network.get_url",
            side_effect=NoURLAvailableError,
        ),
        pytest.raises(HTTPUnauthorized) as exc_info,
    ):
        await request_handler_factory(
            mock_request.app[KEY_HASS],
            Mock(requires_auth=True),
            AsyncMock(),
        )(mock_request)
    assert "WWW-Authenticate" not in exc_info.value.headers


@pytest.fixture
def mock_current_request(
    mock_request: Mock, request_host: str, hass: HomeAssistant
) -> Generator[Mock]:
    """Set the current request context."""
    mock_request.get = Mock(return_value=False)
    mock_request.headers = {hdrs.HOST: request_host}
    mock_request.app = {KEY_HASS: hass}

    token = current_request.set(mock_request)
    yield mock_request
    current_request.reset(token)


@pytest.mark.parametrize(
    ("internal_url", "external_url", "request_host", "expected_url"),
    [
        # Match either internal or external
        ("https://foo.com", "https://example.com", "foo.com:18123", "https://foo.com"),
        ("https://example.com", "https://foo.com", "foo.com:18123", "https://foo.com"),
        # Requests have a port and match external url
        # Note: We currently do not fully properly handle port matching for
        # internal urls. The tests here work because of prefer_external=True. We
        # can improve get_url so that additional cases where the internal url
        # have the same hostname work in future:
        # - Match request to internal url when external url has a port
        # - Match request to external url when internal url has a port
        (
            "https://foo.com",
            "https://foo.com:18123",
            "foo.com:18123",
            "https://foo.com:18123",
        ),
        ("https://foo.com:18123", "https://foo.com", "foo.com", "https://foo.com"),
        (
            "http://192.168.1.2:8123",
            "https://foo.com:18123",
            "192.168.1.2:8123",
            "http://192.168.1.2:8123",
        ),
    ],
    ids=[
        "request_host_matches_internal",
        "request_host_matches_external",
        "internal_no_port_request_external",
        "internal_port_request_external",
        "request_internal_distinct_host",
    ],
)
async def test_requires_auth_www_authenticate_prefer_external(
    mock_current_request: Mock,
    hass: HomeAssistant,
    internal_url: str,
    external_url: str,
    expected_url: str,
) -> None:
    """Test that 401 responses include WWW-Authenticate header matching the requested URL."""
    hass.config.internal_url = internal_url
    hass.config.external_url = external_url

    with pytest.raises(HTTPUnauthorized) as exc_info:
        await request_handler_factory(
            hass,
            Mock(requires_auth=True),
            AsyncMock(),
        )(mock_current_request)

    assert exc_info.value.headers["WWW-Authenticate"] == (
        "Bearer resource_metadata="
        f'"{expected_url}/.well-known/oauth-protected-resource"'
    )
