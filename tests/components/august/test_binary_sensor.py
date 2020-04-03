"""The binary_sensor tests for the august platform."""

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)

from tests.components.august.mocks import (
    _create_august_with_devices,
    _mock_activities_from_fixture,
    _mock_doorbell_from_fixture,
    _mock_lock_from_fixture,
)


async def test_doorsense(hass):
    """Test creation of a lock with doorsense and bridge."""
    lock_one = await _mock_lock_from_fixture(
        hass, "get_lock.online_with_doorsense.json"
    )
    await _create_august_with_devices(hass, [lock_one])

    binary_sensor_online_with_doorsense_name = hass.states.get(
        "binary_sensor.online_with_doorsense_name_open"
    )
    assert binary_sensor_online_with_doorsense_name.state == STATE_ON

    data = {ATTR_ENTITY_ID: "lock.online_with_doorsense_name"}
    assert await hass.services.async_call(
        LOCK_DOMAIN, SERVICE_UNLOCK, data, blocking=True
    )
    await hass.async_block_till_done()

    binary_sensor_online_with_doorsense_name = hass.states.get(
        "binary_sensor.online_with_doorsense_name_open"
    )
    assert binary_sensor_online_with_doorsense_name.state == STATE_ON

    assert await hass.services.async_call(
        LOCK_DOMAIN, SERVICE_LOCK, data, blocking=True
    )
    await hass.async_block_till_done()

    binary_sensor_online_with_doorsense_name = hass.states.get(
        "binary_sensor.online_with_doorsense_name_open"
    )
    assert binary_sensor_online_with_doorsense_name.state == STATE_OFF


async def test_create_doorbell(hass):
    """Test creation of a doorbell."""
    doorbell_one = await _mock_doorbell_from_fixture(hass, "get_doorbell.json")
    await _create_august_with_devices(hass, [doorbell_one])

    binary_sensor_k98gidt45gul_name_motion = hass.states.get(
        "binary_sensor.k98gidt45gul_name_motion"
    )
    assert binary_sensor_k98gidt45gul_name_motion.state == STATE_OFF
    binary_sensor_k98gidt45gul_name_online = hass.states.get(
        "binary_sensor.k98gidt45gul_name_online"
    )
    assert binary_sensor_k98gidt45gul_name_online.state == STATE_ON
    binary_sensor_k98gidt45gul_name_ding = hass.states.get(
        "binary_sensor.k98gidt45gul_name_ding"
    )
    assert binary_sensor_k98gidt45gul_name_ding.state == STATE_OFF
    binary_sensor_k98gidt45gul_name_motion = hass.states.get(
        "binary_sensor.k98gidt45gul_name_motion"
    )
    assert binary_sensor_k98gidt45gul_name_motion.state == STATE_OFF


async def test_create_doorbell_offline(hass):
    """Test creation of a doorbell that is offline."""
    doorbell_one = await _mock_doorbell_from_fixture(hass, "get_doorbell.offline.json")
    await _create_august_with_devices(hass, [doorbell_one])

    binary_sensor_tmt100_name_motion = hass.states.get(
        "binary_sensor.tmt100_name_motion"
    )
    assert binary_sensor_tmt100_name_motion.state == STATE_UNAVAILABLE
    binary_sensor_tmt100_name_online = hass.states.get(
        "binary_sensor.tmt100_name_online"
    )
    assert binary_sensor_tmt100_name_online.state == STATE_OFF
    binary_sensor_tmt100_name_ding = hass.states.get("binary_sensor.tmt100_name_ding")
    assert binary_sensor_tmt100_name_ding.state == STATE_UNAVAILABLE


async def test_create_doorbell_with_motion(hass):
    """Test creation of a doorbell."""
    doorbell_one = await _mock_doorbell_from_fixture(hass, "get_doorbell.json")
    activities = await _mock_activities_from_fixture(
        hass, "get_activity.doorbell_motion.json"
    )
    await _create_august_with_devices(hass, [doorbell_one], activities=activities)

    binary_sensor_k98gidt45gul_name_motion = hass.states.get(
        "binary_sensor.k98gidt45gul_name_motion"
    )
    assert binary_sensor_k98gidt45gul_name_motion.state == STATE_ON
    binary_sensor_k98gidt45gul_name_online = hass.states.get(
        "binary_sensor.k98gidt45gul_name_online"
    )
    assert binary_sensor_k98gidt45gul_name_online.state == STATE_ON
    binary_sensor_k98gidt45gul_name_ding = hass.states.get(
        "binary_sensor.k98gidt45gul_name_ding"
    )
    assert binary_sensor_k98gidt45gul_name_ding.state == STATE_OFF


async def test_doorbell_device_registry(hass):
    """Test creation of a lock with doorsense and bridge ands up in the registry."""
    doorbell_one = await _mock_doorbell_from_fixture(hass, "get_doorbell.offline.json")
    await _create_august_with_devices(hass, [doorbell_one])

    device_registry = await hass.helpers.device_registry.async_get_registry()

    reg_device = device_registry.async_get_device(
        identifiers={("august", "tmt100")}, connections=set()
    )
    assert reg_device.model == "hydra1"
    assert reg_device.name == "tmt100 Name"
    assert reg_device.manufacturer == "August"
    assert reg_device.sw_version == "3.1.0-HYDRC75+201909251139"
