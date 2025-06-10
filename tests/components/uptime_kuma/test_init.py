"""Tests for the Uptime Kuma integration."""

from unittest.mock import AsyncMock

import pytest
from pyuptimekuma import UptimeKumaAuthenticationException, UptimeKumaException

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_pyuptimekuma")
async def test_entry_setup_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test integration setup and unload."""

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        (UptimeKumaAuthenticationException, ConfigEntryState.SETUP_RETRY),
        (UptimeKumaException, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pyuptimekuma: AsyncMock,
    exception: Exception | list[Exception | None],
    state: ConfigEntryState,
) -> None:
    """Test config entry not ready."""

    mock_pyuptimekuma.async_get_monitors.side_effect = exception
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is state
