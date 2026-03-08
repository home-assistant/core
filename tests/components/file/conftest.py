"""Test fixtures for file platform."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.file import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.file.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def is_allowed() -> bool:
    """Parameterize mock_is_allowed_path, default True."""
    return True


@pytest.fixture
def mock_is_allowed_path(hass: HomeAssistant, is_allowed: bool) -> Generator[MagicMock]:
    """Mock is_allowed_path method."""
    with patch.object(
        hass.config, "is_allowed_path", return_value=is_allowed
    ) as allowed_path_mock:
        yield allowed_path_mock


@pytest.fixture
async def setup_ha_file_integration(hass: HomeAssistant):
    """Set up Home Assistant and load File integration."""
    await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {}},
    )
    await hass.async_block_till_done()
