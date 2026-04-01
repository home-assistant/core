"""Tests for Home Assistant View."""

from decimal import Decimal
from http import HTTPStatus
import json
import math
from unittest.mock import AsyncMock, Mock, patch

from aiohttp.web_exceptions import (
    HTTPBadRequest,
    HTTPInternalServerError,
    HTTPUnauthorized,
)
import pytest
import voluptuous as vol

from homeassistant.components.http import KEY_HASS
from homeassistant.components.http.view import (
    HomeAssistantView,
    request_handler_factory,
)
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
        "Unable to serialize to JSON. Bad data found at $.hello=2.0(<class 'decimal.Decimal'>"
        in caplog.text
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
    """Test that 401 responses omit WWW-Authenticate header when no URL is configured."""
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
