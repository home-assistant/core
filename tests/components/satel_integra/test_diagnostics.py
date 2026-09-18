"""Tests for satel integra diagnostics."""

from unittest.mock import AsyncMock

import pytest
from satel_integra import SatelUnexpectedResponseError
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
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


async def test_diagnostics_without_panel_info(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_satel: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test diagnostics when panel information could not be read during setup."""
    mock_satel.read_panel_info.side_effect = SatelUnexpectedResponseError
    await setup_integration(hass, mock_config_entry)

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert diagnostics["panel_info"] is None
    mock_satel.read_panel_info.assert_awaited_once_with()
