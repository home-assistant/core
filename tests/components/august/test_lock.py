"""The lock tests for the august platform."""

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
    STATE_LOCKED,
    STATE_UNKNOWN,
    STATE_UNLOCKED,
)

from tests.components.august.mocks import (
    _create_august_with_devices,
    _mock_doorsense_enabled_august_lock_detail,
    _mock_lock_from_fixture,
)


async def test_lock_device_registry(hass):
    """Test creation of a lock with doorsense and bridge ands up in the registry."""
    lock_one = await _mock_doorsense_enabled_august_lock_detail(hass)
    lock_details = [lock_one]
    await _create_august_with_devices(hass, lock_details)

    device_registry = await hass.helpers.device_registry.async_get_registry()

    reg_device = device_registry.async_get_device(
        identifiers={("august", "online_with_doorsense")}, connections=set()
    )
    assert reg_device.model == "AUG-MD01"
    assert reg_device.sw_version == "undefined-4.3.0-1.8.14"


async def test_one_lock_operation(hass):
    """Test creation of a lock with doorsense and bridge."""
    lock_one = await _mock_doorsense_enabled_august_lock_detail(hass)
    lock_details = [lock_one]
    await _create_august_with_devices(hass, lock_details)

    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")

    assert lock_online_with_doorsense_name.state == STATE_LOCKED

    assert lock_online_with_doorsense_name.attributes.get("battery_level") == 92
    assert (
        lock_online_with_doorsense_name.attributes.get("friendly_name")
        == "online_with_doorsense Name"
    )

    data = {}
    data[ATTR_ENTITY_ID] = "lock.online_with_doorsense_name"
    assert await hass.services.async_call(
        LOCK_DOMAIN, SERVICE_UNLOCK, data, blocking=True
    )

    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")
    assert lock_online_with_doorsense_name.state == STATE_UNLOCKED

    assert lock_online_with_doorsense_name.attributes.get("battery_level") == 92
    assert (
        lock_online_with_doorsense_name.attributes.get("friendly_name")
        == "online_with_doorsense Name"
    )

    assert await hass.services.async_call(
        LOCK_DOMAIN, SERVICE_LOCK, data, blocking=True
    )

    lock_online_with_doorsense_name = hass.states.get("lock.online_with_doorsense_name")
    assert lock_online_with_doorsense_name.state == STATE_LOCKED


async def test_one_lock_unknown_state(hass):
    """Test creation of a lock with doorsense and bridge."""
    lock_one = await _mock_lock_from_fixture(
        hass, "get_lock.online.unknown_state.json",
    )
    lock_details = [lock_one]
    await _create_august_with_devices(hass, lock_details)

    lock_brokenid_name = hass.states.get("lock.brokenid_name")

    assert lock_brokenid_name.state == STATE_UNKNOWN
