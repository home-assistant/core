"""Tests for Ghost integration setup."""

from unittest.mock import AsyncMock

from aioghost.exceptions import GhostAuthError, GhostConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import snapshot_platform


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (GhostAuthError("Invalid API key"), ConfigEntryState.SETUP_ERROR),
        (GhostConnectionError("Connection failed"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_entry_errors(
    hass: HomeAssistant,
    mock_ghost_api: AsyncMock,
    mock_config_entry,
    side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup errors."""
    mock_ghost_api.get_site.side_effect = side_effect

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


async def test_unload_entry(
    hass: HomeAssistant, mock_ghost_api: AsyncMock, mock_config_entry
) -> None:
    """Test unloading config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_ghost_api: AsyncMock,
    mock_config_entry,
) -> None:
    """Snapshot all Ghost sensor entities."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
