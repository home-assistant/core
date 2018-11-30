"""Tests for Home Assistant View."""
from aiohttp.web_exceptions import HTTPInternalServerError
import pytest

from homeassistant.components.http.view import HomeAssistantView


async def test_invalid_json(caplog):
    """Test trying to return invalid JSON."""
    view = HomeAssistantView()

    with pytest.raises(HTTPInternalServerError):
        view.json(float("NaN"))

    assert str(float("NaN")) in caplog.text
