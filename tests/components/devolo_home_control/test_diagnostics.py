"""Tests for the devolo Home Control diagnostics."""

from __future__ import annotations

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import configure_integration
from .mocks import HomeControlMock, HomeControlMockBinarySensor

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup and state change of a climate device."""
    entry = configure_integration(hass)
    gateway_1 = HomeControlMockBinarySensor()
    gateway_2 = HomeControlMock()
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[gateway_1, gateway_2],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED

        result = await get_diagnostics_for_config_entry(hass, hass_client, entry)
        assert result == snapshot
