"""Test Axis diagnostics."""

import pytest
from syrupy import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from .const import API_DISCOVERY_BASIC_DEVICE_INFO

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.parametrize("api_discovery_items", [API_DISCOVERY_BASIC_DEVICE_INFO])
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry_setup: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry_setup
    ) == snapshot(exclude=props("created_at", "modified_at"))
