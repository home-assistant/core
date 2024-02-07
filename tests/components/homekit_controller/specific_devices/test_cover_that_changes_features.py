"""Test for a Home Assistant bridge that changes cover features at runtime."""


from homeassistant.components.cover import CoverEntityFeature
from homeassistant.const import ATTR_SUPPORTED_FEATURES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from ..common import (
    device_config_changed,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_cover_add_feature_at_runtime(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that new features can be added at runtime."""

    # Set up a basic cover that does not support position
    accessories = await setup_accessories_from_file(
        hass, "home_assistant_bridge_cover.json"
    )
    await setup_test_accessories(hass, accessories)

    cover = entity_registry.async_get("cover.family_room_north")
    assert cover.unique_id == "00:00:00:00:00:00_123016423_166"

    cover_state = hass.states.get("cover.family_room_north")
    assert (
        cover_state.attributes[ATTR_SUPPORTED_FEATURES]
        is CoverEntityFeature.OPEN
        | CoverEntityFeature.STOP
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )

    cover = entity_registry.async_get("cover.family_room_north")
    assert cover.unique_id == "00:00:00:00:00:00_123016423_166"

    # Now change the config to remove stop
    accessories = await setup_accessories_from_file(
        hass, "home_assistant_bridge_basic_cover.json"
    )
    await device_config_changed(hass, accessories)

    cover_state = hass.states.get("cover.family_room_north")
    assert (
        cover_state.attributes[ATTR_SUPPORTED_FEATURES]
        is CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )
