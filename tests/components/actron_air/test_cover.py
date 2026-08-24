"""Tests for the Actron Air cover platform."""

from unittest.mock import MagicMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

DAMPER_ENTITY_ID = "cover.living_room_living_room_damper"


async def test_cover_entities(
    hass: HomeAssistant,
    mock_actron_api: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_zone: MagicMock,
) -> None:
    """Test cover entities."""
    status = mock_actron_api.state_manager.get_status.return_value
    status.remote_zone_info = [mock_zone]

    with patch("homeassistant.components.actron_air.PLATFORMS", [Platform.COVER]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_closed_damper(
    hass: HomeAssistant,
    mock_actron_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_zone: MagicMock,
) -> None:
    """Test a damper that is fully closed."""
    status = mock_actron_api.state_manager.get_status.return_value
    status.remote_zone_info = [mock_zone]
    mock_zone.zone_position = 0.0

    with patch("homeassistant.components.actron_air.PLATFORMS", [Platform.COVER]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get(DAMPER_ENTITY_ID)
    assert state is not None
    assert state.state == "closed"
