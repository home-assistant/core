"""Test for the SmartThings scene platform."""

from unittest.mock import AsyncMock

from syrupy import SnapshotAssertion

from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration, snapshot_smartthings_entities

from tests.common import MockConfigEntry


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_smartthings: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    snapshot_smartthings_entities(hass, entity_registry, snapshot, Platform.SCENE)


async def test_activate_scene(
    hass: HomeAssistant,
    mock_smartthings: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test activating a scene."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SCENE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "scene.away"},
        blocking=True,
    )

    mock_smartthings.execute_scene.assert_called_once_with(
        "743b0f37-89b8-476c-aedf-eea8ad8cd29d"
    )
