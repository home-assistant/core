"""Test for the LCN scene platform."""

from unittest.mock import patch

from pypck.lcn_defs import OutputPort, RelayPort

from homeassistant.components.scene import DOMAIN as DOMAIN_SCENE
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MockConfigEntry, MockModuleConnection, MockPchkConnectionManager


async def test_setup_lcn_scene(
    hass: HomeAssistant, lcn_connection: MockPchkConnectionManager
) -> None:
    """Test the setup of switch."""
    for entity_id in (
        "scene.romantic",
        "scene.romantic_transition",
    ):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_UNKNOWN


async def test_entity_attributes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entry: MockConfigEntry,
    lcn_connection: MockPchkConnectionManager,
) -> None:
    """Test the attributes of an entity."""
    entity = entity_registry.async_get("scene.romantic")

    assert entity
    assert entity.unique_id == f"{entry.entry_id}-m000007-0.0"
    assert entity.original_name == "Romantic"

    entity_transition = entity_registry.async_get("scene.romantic_transition")

    assert entity_transition
    assert entity_transition.unique_id == f"{entry.entry_id}-m000007-0.1"
    assert entity_transition.original_name == "Romantic Transition"


@patch.object(MockModuleConnection, "activate_scene")
async def test_scene_activate(
    activate_scene, hass: HomeAssistant, lcn_connection: MockPchkConnectionManager
) -> None:
    """Test the scene is activated."""
    await hass.services.async_call(
        DOMAIN_SCENE,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "scene.romantic"},
        blocking=True,
    )

    state = hass.states.get("scene.romantic")
    assert state is not None
    assert state.attributes["friendly_name"] == "Romantic"
    activate_scene.assert_awaited_with(
        0, 0, [OutputPort.OUTPUT1, OutputPort.OUTPUT2], [RelayPort.RELAY1], None
    )


async def test_unload_config_entry(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    lcn_connection: MockPchkConnectionManager,
) -> None:
    """Test the scene is removed when the config entry is unloaded."""
    await hass.config_entries.async_forward_entry_unload(entry, DOMAIN_SCENE)
    assert hass.states.get("scene.romantic").state == STATE_UNAVAILABLE
