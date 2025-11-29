"""Test Teltonika diagnostics."""

from __future__ import annotations

import pytest

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("mock_teltasync_init", "mock_modems")
async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test diagnostics for the config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result["entry"]["data"]["password"] == "**REDACTED**"

    coordinator = result["coordinator"]
    assert coordinator["last_update_success"] is True
    assert coordinator["modems"]
    modem = coordinator["modems"][0]
    assert modem["id"] == "2-1"
    assert modem["operator"] == "test.operator"

    device = result["device"]
    assert device["manufacturer"] == "Teltonika"
