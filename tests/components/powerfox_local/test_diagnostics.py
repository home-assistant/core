"""Test for Powerfox Local diagnostics."""

from unittest.mock import AsyncMock

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import setup_integration


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_powerfox_local_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Powerfox Local entry diagnostics."""
    await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result == snapshot
