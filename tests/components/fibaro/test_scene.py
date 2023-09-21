"""Test the Fibaro scene platform."""

from pyfibaro.fibaro_scene import SceneModel

from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_platform


async def test_entity_attributes(hass: HomeAssistant, fibaro_scene: SceneModel) -> None:
    """Test that the attributes of the entity are correct."""
    # Arrange
    entity_registry = er.async_get(hass)
    # Act
    await setup_platform(hass, Platform.SCENE, "Room 1", [fibaro_scene])
    # Assert
    entry = entity_registry.async_get("scene.room_1_test_scene")

    assert entry
    assert entry.unique_id == "hc2_111111.scene.1"
    assert entry.original_name == "Room 1 Test scene"


async def test_entity_attributes_without_room(
    hass: HomeAssistant, fibaro_scene: SceneModel
) -> None:
    """Test that the attributes of the entity are correct."""
    # Arrange
    entity_registry = er.async_get(hass)
    # Act
    await setup_platform(hass, Platform.SCENE, None, [fibaro_scene])
    # Assert
    entry = entity_registry.async_get("scene.unknown_test_scene")

    assert entry
    assert entry.unique_id == "hc2_111111.scene.1"


async def test_activate_scene(hass: HomeAssistant, fibaro_scene: SceneModel) -> None:
    """Test activate scene is called."""
    # Arrange
    await setup_platform(hass, Platform.SCENE, "Room 1", [fibaro_scene])
    # Act
    await hass.services.async_call(
        SCENE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "scene.room_1_test_scene"},
        blocking=True,
    )
    # Assert
    assert fibaro_scene.start.call_count == 1
