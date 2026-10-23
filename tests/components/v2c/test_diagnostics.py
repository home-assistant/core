"""Test V2C diagnostics."""

from unittest.mock import AsyncMock

from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_entry_diagnostics(
    hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_v2c_client: AsyncMock,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""

    await init_integration(hass, mock_config_entry)

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    ) == snapshot(exclude=props("created_at", "modified_at"))
