"""Vera tests."""
from unittest.mock import MagicMock

from pyvera import VeraBinarySensor

from homeassistant.core import HomeAssistant

from .common import ComponentFactory


async def test_binary_sensor(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    vera_device = MagicMock(spec=VeraBinarySensor)  # type: VeraBinarySensor
    vera_device.device_id = 1
    vera_device.name = "dev1"
    vera_device.is_tripped = False
    entity_id = "binary_sensor.dev1_1"

    component_data = await vera_component_factory.configure_component(
        hass=hass, devices=(vera_device,)
    )
    controller = component_data.controller

    update_callback = controller.register.call_args_list[0][0][1]

    vera_device.is_tripped = False
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "off"
    controller.register.reset_mock()

    vera_device.is_tripped = True
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "on"
    controller.register.reset_mock()
