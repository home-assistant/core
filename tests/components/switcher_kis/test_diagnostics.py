"""Tests for the diagnostics data provided by Switcher."""

import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import init_integration
from .consts import DUMMY_WATER_HEATER_DEVICE

from tests.components.diagnostics import snapshot_get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_bridge,
    monkeypatch: pytest.MonkeyPatch,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    entry = await init_integration(hass)
    device = DUMMY_WATER_HEATER_DEVICE
    monkeypatch.setattr(device, "last_data_update", "2022-09-28T16:42:12.706017")
    mock_bridge.mock_callbacks([device])
    await hass.async_block_till_done()

    await snapshot_get_diagnostics_for_config_entry(hass, hass_client, entry, snapshot)
