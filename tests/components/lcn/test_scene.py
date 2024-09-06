"""Test for the LCN scene platform."""

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.scene import DOMAIN as DOMAIN_SCENE
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MockConfigEntry, MockModuleConnection, MockPchkConnectionManager


async def test_setup_lcn_scene(
    hass: HomeAssistant,
    lcn_connection: MockPchkConnectionManager,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the setup of switch."""
    for entity_id in (
        "scene.romantic",
        "scene.romantic_transition",
    ):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == snapshot(name=f"{state.entity_id}-state")


async def test_entity_attributes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entry: MockConfigEntry,
    lcn_connection: MockPchkConnectionManager,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the attributes of an entity."""
    entity = entity_registry.async_get("scene.romantic")

    assert entity
    assert entity.unique_id == f"{entry.entry_id}-m000007-0.0"
    assert entity.original_name == snapshot(name=f"{entity.entity_id}-original_name")

    entity_transition = entity_registry.async_get("scene.romantic_transition")

    assert entity_transition
    assert entity_transition.unique_id == f"{entry.entry_id}-m000007-0.1"
    assert entity_transition.original_name == snapshot(
        name=f"{entity_transition.entity_id}-original_name"
    )


async def test_scene_activate(
    hass: HomeAssistant,
    lcn_connection: MockPchkConnectionManager,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the scene is activated."""
    with patch.object(MockModuleConnection, "activate_scene") as activate_scene:
        await hass.services.async_call(
            DOMAIN_SCENE,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "scene.romantic"},
            blocking=True,
        )

        state = hass.states.get("scene.romantic")
        assert state is not None
        assert state.attributes["friendly_name"] == snapshot(
            name=f"{state.entity_id}-friendly-name"
        )

        assert activate_scene.await_args.args == snapshot(name="activate_scene-awaited")


async def test_unload_config_entry(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    lcn_connection: MockPchkConnectionManager,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the scene is removed when the config entry is unloaded."""
    await hass.config_entries.async_forward_entry_unload(entry, DOMAIN_SCENE)
    state = hass.states.get("scene.romantic")
    assert state.state == snapshot(name=f"{state.entity_id}-state")
