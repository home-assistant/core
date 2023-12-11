"""Common fixtures for the Sveriges Radio tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.sveriges_radio.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sveriges_radio.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="config_entry")
def config_entry_fixture():
    """Create a mock Sveriges Radio config entry."""
    return MockConfigEntry(domain=DOMAIN, title="Sveriges_radio")


@pytest.fixture
def async_setup_sr(hass: HomeAssistant, config_entry):
    """Return a coroutine to set up a Sveriges Radio integration instance on demand."""

    async def _wrapper():
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return _wrapper
