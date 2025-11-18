"""Fixtures for Home Assistant Labs tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.labs import async_setup
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.labs.async_setup_entry",
        return_value=True,
    ):
        yield


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_setup_entry: None,
) -> MockConfigEntry:
    """Set up the Labs integration in Home Assistant."""
    # Labs integration doesn't use config entries - it's automatically loaded
    # Just ensure it's set up
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    return None
