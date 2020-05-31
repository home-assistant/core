"""Tests for Home Assistant View."""
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

from tests.async_mock import AsyncMock, Mock


@pytest.fixture
def mock_request():
    """Mock a request."""
    return Mock(app={"hass": Mock(is_running=True)}, match_info={})


async def test_invalid_json(caplog):
    """Test trying to return invalid JSON."""
    view = HomeAssistantView()

    with pytest.raises(HTTPInternalServerError):
        view.json(float("NaN"))

    assert str(float("NaN")) in caplog.text


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
