"""Tests for satel integra diagnostics."""

from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.parametrize(
    ("config_entry_fixture"),
    [
        ("mock_config_entry_with_subentries"),
        ("mock_config_entry_with_temperature_zone"),
    ],
)
async def test_diagnostics(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    hass_client: ClientSessionGenerator,
    mock_satel: AsyncMock,
    request: pytest.FixtureRequest,
    config_entry_fixture: str,
) -> None:
    """Test diagnostics for config entry."""
    entry = request.getfixturevalue(config_entry_fixture)
    await setup_integration(hass, entry)

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diagnostics == snapshot(exclude=props("created_at", "modified_at", "id"))
