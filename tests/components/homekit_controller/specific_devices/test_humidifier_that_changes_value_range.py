"""Test for a Home Assistant bridge that changes humidifier min/max at runtime."""


from homeassistant.components.humidifier import ATTR_MAX_HUMIDITY, ATTR_MIN_HUMIDITY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from ..common import (
    device_config_changed,
    setup_accessories_from_file,
    setup_test_accessories,
)


async def test_humidifier_change_range_at_runtime(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that min max can be changed at runtime."""

    # Set up a basic humidifier
    accessories = await setup_accessories_from_file(
        hass, "home_assistant_bridge_humidifier.json"
    )
    await setup_test_accessories(hass, accessories)

    humidifier = entity_registry.async_get("humidifier.humidifier_182a")
    assert humidifier.unique_id == "00:00:00:00:00:00_293334836_8"

    humidifier_state = hass.states.get("humidifier.humidifier_182a")
    assert humidifier_state.attributes[ATTR_MIN_HUMIDITY] == 0
    assert humidifier_state.attributes[ATTR_MAX_HUMIDITY] == 100

    cover = entity_registry.async_get("humidifier.humidifier_182a")
    assert cover.unique_id == "00:00:00:00:00:00_293334836_8"

    # Now change min/max values
    accessories = await setup_accessories_from_file(
        hass, "home_assistant_bridge_humidifier_new_range.json"
    )
    await device_config_changed(hass, accessories)

    humidifier_state = hass.states.get("humidifier.humidifier_182a")
    assert humidifier_state.attributes[ATTR_MIN_HUMIDITY] == 20
    assert humidifier_state.attributes[ATTR_MAX_HUMIDITY] == 80
