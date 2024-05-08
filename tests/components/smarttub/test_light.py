"""Test the SmartTub light platform."""

import pytest
from smarttub import SpaLight

from homeassistant.core import HomeAssistant


# the light in light_zone should have initial state light_state. we will call
# service_name with service_params, and expect the resultant call to
# SpaLight.set_mode to have set_mode_args parameters
@pytest.mark.parametrize(
    ("light_zone", "light_state", "service_name", "service_params", "set_mode_args"),
    [
        (1, "off", "turn_on", {}, (SpaLight.LightMode.PURPLE, 50)),
        (1, "off", "turn_on", {"brightness": 255}, (SpaLight.LightMode.PURPLE, 100)),
        (2, "on", "turn_off", {}, (SpaLight.LightMode.OFF, 0)),
    ],
)
async def test_light(
    spa,
    setup_entry,
    hass: HomeAssistant,
    light_zone,
    light_state,
    service_name,
    service_params,
    set_mode_args,
) -> None:
    """Test light entity."""

    entity_id = f"light.{spa.brand}_{spa.model}_light_{light_zone}"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == light_state

    status = await spa.get_status_full()
    light: SpaLight = next(light for light in status.lights if light.zone == light_zone)

    await hass.services.async_call(
        "light",
        service_name,
        {"entity_id": entity_id, **service_params},
        blocking=True,
    )
    light.set_mode.assert_called_with(*set_mode_args)
