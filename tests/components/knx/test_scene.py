"""Test KNX scene."""

from homeassistant.components.knx.const import KNX_ADDRESS
from homeassistant.components.knx.schema import SceneSchema
from homeassistant.const import CONF_ENTITY_CATEGORY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory

from .conftest import KNXTestKit


async def test_activate_knx_scene(hass: HomeAssistant, knx: KNXTestKit):
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
    assert len(hass.states.async_all()) == 1

    registry = er.async_get(hass)
    entity = registry.async_get("scene.test")
    assert entity.entity_category is EntityCategory.DIAGNOSTIC
    assert entity.unique_id == "1/1/1_24"

    await hass.services.async_call(
        "scene", "turn_on", {"entity_id": "scene.test"}, blocking=True
    )

    # assert scene was called on bus
    await knx.assert_write("1/1/1", (0x17,))
