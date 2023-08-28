"""Test Yale Smart Living diagnostics."""
from __future__ import annotations

from unittest.mock import Mock

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    load_config_entry: tuple[MockConfigEntry, Mock],
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    entry = load_config_entry[0]

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diag == snapshot
