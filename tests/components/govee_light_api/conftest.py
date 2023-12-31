"""Tests configuration for Govee Local API."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.govee_light_api.coordinator import GoveeController


@pytest.fixture(name="mock_govee_api")
def fixture_mock_govee_api():
    """Set up Govee Local API fixture."""
    mock_api = AsyncMock(spec=GoveeController)
    mock_api.start = AsyncMock()
    mock_api.turn_on_off = AsyncMock()
    mock_api.set_brightness = AsyncMock()
    mock_api.set_color = AsyncMock()
    mock_api._async_update_data = AsyncMock()
    return mock_api


@pytest.fixture(name="mock_setup_entry")
def fixture_mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.govee_light_api.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
