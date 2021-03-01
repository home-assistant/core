"""Test the SmartTub light platform."""

from smarttub import SpaLight


async def test_light(spa, setup_entry, hass):
    """Test light entity."""

    for light in spa.get_lights.return_value:
        entity_id = f"light.{spa.brand}_{spa.model}_light_{light.zone}"
        state = hass.states.get(entity_id)
        assert state is not None
        if light.mode == SpaLight.LightMode.OFF:
            assert state.state == "off"
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
            assert state.state == "on"
            await hass.services.async_call(
                "light",
                "turn_off",
                {"entity_id": entity_id},
                blocking=True,
            )
