"""The tests for the Ring button platform."""

from unittest.mock import Mock

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import MockConfigEntry, setup_platform

from tests.common import snapshot_platform


async def test_states(
    hass: HomeAssistant,
    mock_ring_client: Mock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test states."""
    mock_config_entry.add_to_hass(hass)
    await setup_platform(hass, Platform.BUTTON)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_button_opens_door(
    hass: HomeAssistant,
    mock_ring_client,
    mock_ring_devices,
) -> None:
    """Tests the door open button works correctly."""
    await setup_platform(hass, Platform.BUTTON)

    mock_intercom = mock_ring_devices.get_device(185036587)
    mock_intercom.async_open_door.assert_not_called()

    await hass.services.async_call(
        "button", "press", {"entity_id": "button.ingress_open_door"}, blocking=True
    )

    await hass.async_block_till_done(wait_background_tasks=True)
    mock_intercom.async_open_door.assert_called_once()
