"""Test the NeoPool diagnostics."""

from unittest.mock import MagicMock

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.neopool.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Test config entry diagnostics output is stable and redacts host/port."""
    await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result == snapshot(
        exclude=props(
            "created_at",
            "modified_at",
            "entry_id",
            "last_update_time",
            "update_interval",
        )
    )


async def test_entry_diagnostics_without_runtime_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Diagnostics returns 'not loaded' when the entry has no coordinator yet.

    This branch is reached if diagnostics is queried for an entry that has
    been added but never loaded (e.g. it failed setup and was retried).
    """
    mock_config_entry.add_to_hass(hass)
    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert result["coordinator"] == {"status": "not loaded"}
    assert result["config_entry"]["data"]["host"] == "**REDACTED**"
