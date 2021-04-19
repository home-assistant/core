"""Vera tests."""
from unittest.mock import MagicMock

import pyvera as pv

from homeassistant.const import STATE_LOCKED, STATE_UNLOCKED
from homeassistant.core import HomeAssistant

from .common import ComponentFactory, new_simple_controller_config


async def test_lock(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    vera_device: pv.VeraLock = MagicMock(spec=pv.VeraLock)
    vera_device.device_id = 1
    vera_device.vera_device_id = vera_device.device_id
    vera_device.comm_failure = False
    vera_device.name = "dev1"
    vera_device.category = pv.CATEGORY_LOCK
    vera_device.is_locked = MagicMock(return_value=False)
    entity_id = "lock.dev1_1"

    component_data = await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(devices=(vera_device,)),
    )
    update_callback = component_data.controller_data[0].update_callback

    assert hass.states.get(entity_id).state == STATE_UNLOCKED

    await hass.services.async_call(
        "lock",
        "lock",
        {"entity_id": entity_id},
    )
    await hass.async_block_till_done()
    vera_device.lock.assert_called()
    vera_device.is_locked.return_value = True
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_LOCKED

    await hass.services.async_call(
        "lock",
        "unlock",
        {"entity_id": entity_id},
    )
    await hass.async_block_till_done()
    vera_device.unlock.assert_called()
    vera_device.is_locked.return_value = False
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNLOCKED
