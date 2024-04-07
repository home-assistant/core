"""Test for a Home Assistant bridge that changes light features at runtime."""

from homeassistant.components.light import ATTR_SUPPORTED_COLOR_MODES, ColorMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from ..common import (
    device_config_changed,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_light_add_feature_at_runtime(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that new features can be added at runtime."""

    # Set up a basic light that does not support color
    accessories = await setup_accessories_from_file(
        hass, "home_assistant_bridge_basic_light.json"
    )
    await setup_test_accessories(hass, accessories)

    light = entity_registry.async_get("light.laundry_smoke_ed78")
    assert light.unique_id == "00:00:00:00:00:00_3982136094_608"

    light_state = hass.states.get("light.laundry_smoke_ed78")
    assert light_state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]

    light = entity_registry.async_get("light.laundry_smoke_ed78")
    assert light.unique_id == "00:00:00:00:00:00_3982136094_608"

    # Now add hue and saturation
    accessories = await setup_accessories_from_file(
        hass, "home_assistant_bridge_light.json"
    )
    await device_config_changed(hass, accessories)

    light_state = hass.states.get("light.laundry_smoke_ed78")
    assert light_state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
    ]
