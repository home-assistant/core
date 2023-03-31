"""The button tests for the august platform."""
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .mocks import _create_august_api_with_devices, _mock_lock_from_fixture


async def test_wake_lock(hass: HomeAssistant) -> None:
    """Test creation of a lock and wake it."""
    lock_one = await _mock_lock_from_fixture(
        hass, "get_lock.online_with_doorsense.json"
    )
    _, api_instance = await _create_august_api_with_devices(hass, [lock_one])
    entity_id = "button.online_with_doorsense_name_wake"
    binary_sensor_online_with_doorsense_name = hass.states.get(entity_id)
    assert binary_sensor_online_with_doorsense_name is not None
    api_instance.async_status_async.reset_mock()
    assert await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()
    api_instance.async_status_async.assert_called_once()
