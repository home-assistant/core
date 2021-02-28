"""Test the SmartTub light platform."""

import pytest
from smarttub import SpaLight


@pytest.mark.parametrize("light_zone,light_state", [(1, "off"), (2, "on")])
async def test_light(spa, setup_entry, hass, light_zone, light_state):
    """Test light entity."""

    entity_id = f"light.{spa.brand}_{spa.model}_light_{light_zone}"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == light_state

    light: SpaLight = next(
        light for light in await spa.get_lights() if light.zone == light_zone
    )

    if state.state == "off":
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": entity_id},
            blocking=True,
        )
        light.set_mode.assert_called()

        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": entity_id, "brightness": 255},
            blocking=True,
        )
        light.set_mode.assert_called_with(SpaLight.LightMode.PURPLE, 100)

    else:
        await hass.services.async_call(
            "light",
            "turn_off",
            {"entity_id": entity_id},
            blocking=True,
        )
