"""Test KNX scene."""

import pytest

from homeassistant.components.knx.const import KNX_ADDRESS
from homeassistant.components.knx.schema import SceneSchema
from homeassistant.const import (
    CONF_ENTITY_CATEGORY,
    CONF_NAME,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import KnxEntityGenerator
from .conftest import KNXTestKit

from tests.common import async_capture_events


async def test_activate_knx_scene(
    hass: HomeAssistant, knx: KNXTestKit, entity_registry: er.EntityRegistry
) -> None:
    """Test KNX scene."""
    await knx.setup_integration(
        {
            SceneSchema.PLATFORM: [
                {
                    CONF_NAME: "test",
                    SceneSchema.CONF_SCENE_NUMBER: 24,
                    KNX_ADDRESS: "1/1/1",
                    CONF_ENTITY_CATEGORY: EntityCategory.DIAGNOSTIC,
                },
            ]
        }
    )

    entity = entity_registry.async_get("scene.test")
    assert entity.entity_category is EntityCategory.DIAGNOSTIC
    assert entity.unique_id == "1/1/1_24"

    events = async_capture_events(hass, "state_changed")

    # activate scene from HA
    await hass.services.async_call(
        "scene", "turn_on", {"entity_id": "scene.test"}, blocking=True
    )
    await knx.assert_write("1/1/1", (0x17,))
    assert len(events) == 1
    # consecutive call from HA
    await hass.services.async_call(
        "scene", "turn_on", {"entity_id": "scene.test"}, blocking=True
    )
    await knx.assert_write("1/1/1", (0x17,))
    assert len(events) == 2

    # scene activation from bus
    await knx.receive_write("1/1/1", (0x17,))
    assert len(events) == 3
    # same scene number consecutive call
    await knx.receive_write("1/1/1", (0x17,))
    assert len(events) == 4
    # different scene number - should not be recorded
    await knx.receive_write("1/1/1", (0x00,))
    assert len(events) == 4
    # learn request for this scene number - should not be recorded
    await knx.receive_write("1/1/1", (0x97,))
    assert len(events) == 4
    # activation after a learn request is recorded again
    await knx.receive_write("1/1/1", (0x17,))
    assert len(events) == 5


async def test_save_knx_scene(
    hass: HomeAssistant, knx: KNXTestKit, caplog: pytest.LogCaptureFixture
) -> None:
    """Test saving a KNX scene sends a DPT 18.001 learn telegram."""
    await knx.setup_integration(
        {
            SceneSchema.PLATFORM: [
                {
                    CONF_NAME: "test",
                    SceneSchema.CONF_SCENE_NUMBER: 24,
                    KNX_ADDRESS: "1/1/1",
                },
            ]
        }
    )

    events = async_capture_events(hass, "state_changed")

    await hass.services.async_call(
        "knx", "save_scene", {"entity_id": "scene.test"}, blocking=True
    )
    # learn bit set on the 0-based raw scene number
    await knx.assert_write("1/1/1", (0x97,))
    # saving is not an activation
    assert len(events) == 0
    # the outgoing telegram is decodable by the device processing it
    assert "Can not process" not in caplog.text


async def test_scene_ui_create(
    hass: HomeAssistant,
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
) -> None:
    """Test creating a scene."""
    await knx.setup_integration()
    await create_ui_entity(
        platform=Platform.SCENE,
        entity_data={"name": "test"},
        knx_data={
            "ga_scene": {"write": "1/1/1"},
            "scene_number": 5,
        },
    )
    # activate scene from HA
    await hass.services.async_call(
        "scene", "turn_on", {"entity_id": "scene.test"}, blocking=True
    )
    await knx.assert_write("1/1/1", (0x04,))  # raw scene number is 0-based


async def test_scene_ui_load(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test loading a scene from storage."""
    await knx.setup_integration(config_store_fixture="config_store_scene.json")
    # activate scene from HA
    await hass.services.async_call(
        "scene", "turn_on", {"entity_id": "scene.test"}, blocking=True
    )
    await knx.assert_write("1/1/1", (0x0B,))
