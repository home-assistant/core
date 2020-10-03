"""Vera tests."""
import pyvera as pv

from homeassistant.const import STATE_LOCKED, STATE_UNLOCKED
from homeassistant.core import HomeAssistant

from .common import ComponentFactory, new_simple_controller_config

from tests.async_mock import MagicMock


async def test_lock(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    vera_device = MagicMock(spec=pv.VeraLock)  # type: pv.VeraLock
    vera_device.device_id = 1
    vera_device.name = "dev1"
    vera_device.category = pv.CATEGORY_LOCK
    vera_device.is_locked = MagicMock(return_value=False)
    entity_id = "lock.dev1_1"

    component_data = await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(devices=(vera_device,)),
    )
    update_callback = component_data.controller_data.update_callback

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
