"""Test KNX scene."""

from homeassistant.components.knx.const import KNX_ADDRESS
from homeassistant.components.knx.schema import SceneSchema
from homeassistant.const import CONF_ENTITY_CATEGORY, CONF_NAME, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

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
