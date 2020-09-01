"""Vera tests."""
import pyvera as pv

from homeassistant.core import HomeAssistant

from .common import ComponentFactory, new_simple_controller_config

from tests.async_mock import MagicMock


async def test_switch(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    vera_device = MagicMock(spec=pv.VeraSwitch)  # type: pv.VeraSwitch
    vera_device.device_id = 1
    vera_device.name = "dev1"
    vera_device.category = pv.CATEGORY_SWITCH
    vera_device.is_switched_on = MagicMock(return_value=False)
    entity_id = "switch.dev1_1"

    component_data = await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(devices=(vera_device,)),
    )
    update_callback = component_data.controller_data.update_callback

    assert hass.states.get(entity_id).state == "off"

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": entity_id},
    )
    await hass.async_block_till_done()
    vera_device.switch_on.assert_called()
    vera_device.is_switched_on.return_value = True
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "on"

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": entity_id},
    )
    await hass.async_block_till_done()
    vera_device.switch_off.assert_called()
    vera_device.is_switched_on.return_value = False
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "off"
