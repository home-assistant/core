"""Test fixtures for TheSilentWave."""

from collections.abc import Awaitable, Callable, Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.thesilentwave.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_unique_id",
        title="TheSilentWave",
        data={
            CONF_HOST: "192.168.1.100",
        },
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
def mock_silent_wave_client() -> Generator[AsyncMock]:
    """Return a mocked SilentWaveClient."""
    with patch(
        "homeassistant.components.thesilentwave.coordinator.SilentWaveClient",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value
        client.get_status = AsyncMock(return_value="on")
        yield client


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_silent_wave_client: AsyncMock,
) -> None:
    """Set up the integration."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
async def setup_integration_deferred(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_silent_wave_client: AsyncMock,
) -> Callable[[], Awaitable]:
    """Set up the integration."""

    async def run() -> None:
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return run
