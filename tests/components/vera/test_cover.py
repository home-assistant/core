"""Vera tests."""

from unittest.mock import MagicMock

import pyvera as pv

from homeassistant.core import HomeAssistant

from .common import ComponentFactory, new_simple_controller_config


async def test_cover(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    vera_device: pv.VeraCurtain = MagicMock(spec=pv.VeraCurtain)
    vera_device.device_id = 1
    vera_device.vera_device_id = vera_device.device_id
    vera_device.comm_failure = False
    vera_device.name = "dev1"
    vera_device.category = pv.CATEGORY_CURTAIN
    vera_device.is_closed = False
    vera_device.get_level.return_value = 0
    entity_id = "cover.dev1_1"

    component_data = await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(devices=(vera_device,)),
    )
    update_callback = component_data.controller_data[0].update_callback

    assert hass.states.get(entity_id).state == "closed"
    assert hass.states.get(entity_id).attributes["current_position"] == 0

    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": entity_id},
    )
    await hass.async_block_till_done()
    vera_device.open.assert_called()
    vera_device.is_open.return_value = True
    vera_device.get_level.return_value = 100
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "open"
    assert hass.states.get(entity_id).attributes["current_position"] == 100

    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": entity_id, "position": 50},
    )
    await hass.async_block_till_done()
    vera_device.set_level.assert_called_with(50)
    vera_device.is_open.return_value = True
    vera_device.get_level.return_value = 50
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "open"
    assert hass.states.get(entity_id).attributes["current_position"] == 50

    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": entity_id},
    )
    await hass.async_block_till_done()
    vera_device.stop.assert_called()
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "open"
    assert hass.states.get(entity_id).attributes["current_position"] == 50

    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": entity_id},
    )
    await hass.async_block_till_done()
    vera_device.close.assert_called()
    vera_device.is_open.return_value = False
    vera_device.get_level.return_value = 00
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "closed"
    assert hass.states.get(entity_id).attributes["current_position"] == 00
