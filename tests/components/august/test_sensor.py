"""The sensor tests for the august platform."""

from tests.components.august.mocks import (
    _create_august_with_devices,
    _mock_doorbell_from_fixture,
    _mock_lock_from_fixture,
)


async def test_create_doorbell(hass):
    """Test creation of a doorbell."""
    doorbell_one = await _mock_doorbell_from_fixture(hass, "get_doorbell.json")
    await _create_august_with_devices(hass, [doorbell_one])

    sensor_k98gidt45gul_name_battery = hass.states.get(
        "sensor.k98gidt45gul_name_battery"
    )
    assert sensor_k98gidt45gul_name_battery.state == "96"
    assert sensor_k98gidt45gul_name_battery.attributes["unit_of_measurement"] == "%"


async def test_create_doorbell_offline(hass):
    """Test creation of a doorbell that is offline."""
    doorbell_one = await _mock_doorbell_from_fixture(hass, "get_doorbell.offline.json")
    await _create_august_with_devices(hass, [doorbell_one])
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    sensor_tmt100_name_battery = hass.states.get("sensor.tmt100_name_battery")
    assert sensor_tmt100_name_battery.state == "81"
    assert sensor_tmt100_name_battery.attributes["unit_of_measurement"] == "%"

    entry = entity_registry.async_get("sensor.tmt100_name_battery")
    assert entry
    assert entry.unique_id == "tmt100_device_battery"


async def test_create_doorbell_hardwired(hass):
    """Test creation of a doorbell that is hardwired without a battery."""
    doorbell_one = await _mock_doorbell_from_fixture(
        hass, "get_doorbell.nobattery.json"
    )
    await _create_august_with_devices(hass, [doorbell_one])

    sensor_tmt100_name_battery = hass.states.get("sensor.tmt100_name_battery")
    assert sensor_tmt100_name_battery is None


async def test_create_lock_with_linked_keypad(hass):
    """Test creation of a lock with a linked keypad that both have a battery."""
    lock_one = await _mock_lock_from_fixture(hass, "get_lock.doorsense_init.json")
    await _create_august_with_devices(hass, [lock_one])
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    sensor_a6697750d607098bae8d6baa11ef8063_name_battery = hass.states.get(
        "sensor.a6697750d607098bae8d6baa11ef8063_name_battery"
    )
    assert sensor_a6697750d607098bae8d6baa11ef8063_name_battery.state == "88"
    assert (
        sensor_a6697750d607098bae8d6baa11ef8063_name_battery.attributes[
            "unit_of_measurement"
        ]
        == "%"
    )
    entry = entity_registry.async_get(
        "sensor.a6697750d607098bae8d6baa11ef8063_name_battery"
    )
    assert entry
    assert entry.unique_id == "A6697750D607098BAE8D6BAA11EF8063_device_battery"

    sensor_a6697750d607098bae8d6baa11ef8063_name_keypad_battery = hass.states.get(
        "sensor.a6697750d607098bae8d6baa11ef8063_name_keypad_battery"
    )
    assert sensor_a6697750d607098bae8d6baa11ef8063_name_keypad_battery.state == "60"
    assert (
        sensor_a6697750d607098bae8d6baa11ef8063_name_keypad_battery.attributes[
            "unit_of_measurement"
        ]
        == "%"
    )
    entry = entity_registry.async_get(
        "sensor.a6697750d607098bae8d6baa11ef8063_name_keypad_battery"
    )
    assert entry
    assert entry.unique_id == "A6697750D607098BAE8D6BAA11EF8063_linked_keypad_battery"
