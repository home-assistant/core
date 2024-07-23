"""Fixtures for the Switch as X integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
async def setup_homeassistant(hass: HomeAssistant):
    """Set up the homeassistant integration."""
    await async_setup_component(hass, "homeassistant", {})


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.switch_as_x.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup
