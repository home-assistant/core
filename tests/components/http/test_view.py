"""Tests for Home Assistant View."""
from http import HTTPStatus
import json
from unittest.mock import AsyncMock, Mock

from aiohttp.web_exceptions import (
    HTTPBadRequest,
    HTTPInternalServerError,
    HTTPUnauthorized,
)
import pytest
import voluptuous as vol

from homeassistant.components.http.view import (
    HomeAssistantView,
    request_handler_factory,
)
from homeassistant.exceptions import ServiceNotFound, Unauthorized


@pytest.fixture
def mock_request():
    """Mock a request."""
    return Mock(app={"hass": Mock(is_stopping=False)}, match_info={})


@pytest.fixture
def mock_request_with_stopping():
    """Mock a request."""
    return Mock(app={"hass": Mock(is_stopping=True)}, match_info={})


async def test_invalid_json(caplog):
    """Test trying to return invalid JSON."""
    view = HomeAssistantView()

    with pytest.raises(HTTPInternalServerError):
        view.json(rb"\ud800")

    assert "Unable to serialize to JSON" in caplog.text


async def test_nan_serialized_to_null(caplog):
    """Test nan serialized to null JSON."""
    view = HomeAssistantView()
    response = view.json(float("NaN"))
    assert json.loads(response.body.decode("utf-8")) is None


async def test_handling_unauthorized(mock_request):
    """Test handling unauth exceptions."""
    with pytest.raises(HTTPUnauthorized):
        await request_handler_factory(
            Mock(requires_auth=False), AsyncMock(side_effect=Unauthorized)
        )(mock_request)


async def test_handling_invalid_data(mock_request):
    """Test handling unauth exceptions."""
    with pytest.raises(HTTPBadRequest):
        await request_handler_factory(
            Mock(requires_auth=False), AsyncMock(side_effect=vol.Invalid("yo"))
        )(mock_request)


async def test_handling_service_not_found(mock_request):
    """Test handling unauth exceptions."""
    with pytest.raises(HTTPInternalServerError):
        await request_handler_factory(
            Mock(requires_auth=False),
            AsyncMock(side_effect=ServiceNotFound("test", "test")),
        )(mock_request)


async def test_not_running(mock_request_with_stopping):
    """Test we get a 503 when not running."""
    response = await request_handler_factory(
        Mock(requires_auth=False), AsyncMock(side_effect=Unauthorized)
    )(mock_request_with_stopping)
    assert response.status == HTTPStatus.SERVICE_UNAVAILABLE
