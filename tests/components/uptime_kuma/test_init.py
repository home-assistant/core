"""Tests for the Uptime Kuma integration."""

from unittest.mock import AsyncMock

import pytest
from pythonkuma import UptimeKumaAuthenticationException, UptimeKumaException

from homeassistant.components.uptime_kuma.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_pythonkuma")
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
        (UptimeKumaAuthenticationException, ConfigEntryState.SETUP_ERROR),
        (UptimeKumaException, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pythonkuma: AsyncMock,
    exception: Exception,
    state: ConfigEntryState,
) -> None:
    """Test config entry not ready."""

    mock_pythonkuma.metrics.side_effect = exception
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is state


async def test_config_reauth_flow(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pythonkuma: AsyncMock,
) -> None:
    """Test config entry auth error starts reauth flow."""

    mock_pythonkuma.metrics.side_effect = UptimeKumaAuthenticationException
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == config_entry.entry_id
