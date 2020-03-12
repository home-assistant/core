"""Vera tests."""
from unittest.mock import MagicMock

from pyvera import CATEGORY_LOCK, VeraLock

from homeassistant.const import STATE_LOCKED, STATE_UNLOCKED
from homeassistant.core import HomeAssistant

from .common import ComponentFactory


async def test_lock(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    vera_device = MagicMock(spec=VeraLock)  # type: VeraLock
    vera_device.device_id = 1
    vera_device.name = "dev1"
    vera_device.category = CATEGORY_LOCK
    vera_device.is_locked = MagicMock(return_value=False)
    entity_id = "lock.dev1_1"

    component_data = await vera_component_factory.configure_component(
        hass=hass, devices=(vera_device,),
    )
    controller = component_data.controller
    update_callback = controller.register.call_args_list[0][0][1]

    assert hass.states.get(entity_id).state == STATE_UNLOCKED

    await hass.services.async_call(
        "lock", "lock", {"entity_id": entity_id},
    )
    await hass.async_block_till_done()
    vera_device.lock.assert_called()
    vera_device.is_locked.return_value = True
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_LOCKED

    await hass.services.async_call(
        "lock", "unlock", {"entity_id": entity_id},
    )
    await hass.async_block_till_done()
    vera_device.unlock.assert_called()
    vera_device.is_locked.return_value = False
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNLOCKED
