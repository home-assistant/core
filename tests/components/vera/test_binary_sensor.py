"""Vera tests."""
import pyvera as pv

from homeassistant.core import HomeAssistant

from .common import ComponentFactory, new_simple_controller_config

from tests.async_mock import MagicMock


async def test_binary_sensor(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    vera_device = MagicMock(spec=pv.VeraBinarySensor)  # type: pv.VeraBinarySensor
    vera_device.device_id = 1
    vera_device.vera_device_id = 1
    vera_device.name = "dev1"
    vera_device.is_tripped = False
    entity_id = "binary_sensor.dev1_1"

    component_data = await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(devices=(vera_device,)),
    )
    update_callback = component_data.controller_data.update_callback

    vera_device.is_tripped = False
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "off"

    vera_device.is_tripped = True
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "on"
