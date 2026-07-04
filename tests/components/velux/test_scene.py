"""Test Velux scene entities."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN, SERVICE_TURN_ON
from homeassistant.components.velux import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import AsyncMock, MockConfigEntry, snapshot_platform


@pytest.fixture
def platform() -> Platform:
    """Fixture to specify platform to test."""
    return Platform.SCENE


@pytest.mark.usefixtures("setup_integration")
async def test_scene_snapshot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the scene entity (registry + state)."""
    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry.entry_id,
    )

    # Get the scene entity setup and test device association
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entity_entries) == 1
    entry = entity_entries[0]

    assert entry.device_id is not None
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry is not None
    # Scenes are associated with the gateway device
    assert (DOMAIN, f"gateway_{mock_config_entry.entry_id}") in device_entry.identifiers
    assert device_entry.via_device_id is None


@pytest.mark.usefixtures("setup_integration")
async def test_scene_activation(
    hass: HomeAssistant,
    mock_scene: AsyncMock,
) -> None:
    """Test successful scene activation."""

    # activate the scene via service call
    await hass.services.async_call(
        SCENE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "scene.klf_200_gateway_test_scene"},
        blocking=True,
    )

    # Verify the run method was called
    mock_scene.run.assert_awaited_once_with(wait_for_completion=False)
