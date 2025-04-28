"""Test singleton helper."""

from typing import Any
from unittest.mock import Mock

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import singleton


@pytest.fixture
def mock_hass():
    """Mock hass fixture."""
    return Mock(data={})


@pytest.mark.parametrize("result", [object(), {}, []])
async def test_singleton_async(mock_hass: HomeAssistant, result: Any) -> None:
    """Test singleton with async function."""

    @singleton.singleton("test_key")
    async def something(hass: HomeAssistant) -> Any:
        return result

    result1 = await something(mock_hass)
    result2 = await something(mock_hass)
    assert result1 is result
    assert result1 is result2
    assert "test_key" in mock_hass.data
    assert mock_hass.data["test_key"] is result1


@pytest.mark.parametrize("result", [object(), {}, []])
def test_singleton(mock_hass: HomeAssistant, result: Any) -> None:
    """Test singleton with function."""

    @singleton.singleton("test_key")
    def something(hass: HomeAssistant) -> Any:
        return result

    result1 = something(mock_hass)
    result2 = something(mock_hass)
    assert result1 is result
    assert result1 is result2
    assert "test_key" in mock_hass.data
    assert mock_hass.data["test_key"] is result1
