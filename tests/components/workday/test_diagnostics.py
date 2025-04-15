"""Test Workday diagnostics."""

from __future__ import annotations

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from . import TEST_CONFIG_ADD_REMOVE_DATE_RANGE, init_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    entry = await init_integration(hass, TEST_CONFIG_ADD_REMOVE_DATE_RANGE)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diag == snapshot(
        exclude=props("full_features", "created_at", "modified_at"),
    )
