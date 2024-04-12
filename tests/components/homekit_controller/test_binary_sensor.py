"""Basic checks for HomeKit motion sensors and contact sensors."""

from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import get_next_aid, setup_test_component


def create_motion_sensor_service(accessory):
    """Define motion characteristics as per page 225 of HAP spec."""
    service = accessory.add_service(ServicesTypes.MOTION_SENSOR)

    cur_state = service.add_char(CharacteristicsTypes.MOTION_DETECTED)
    cur_state.value = 0


async def test_motion_sensor_read_state(hass: HomeAssistant) -> None:
    """Test that we can read the state of a HomeKit motion sensor accessory."""
    helper = await setup_test_component(hass, create_motion_sensor_service)

    await helper.async_update(
        ServicesTypes.MOTION_SENSOR, {CharacteristicsTypes.MOTION_DETECTED: False}
    )
    state = await helper.poll_and_get_state()
    assert state.state == "off"

    await helper.async_update(
        ServicesTypes.MOTION_SENSOR, {CharacteristicsTypes.MOTION_DETECTED: True}
    )
    state = await helper.poll_and_get_state()
    assert state.state == "on"

    assert state.attributes["device_class"] == BinarySensorDeviceClass.MOTION


def create_contact_sensor_service(accessory):
    """Define contact characteristics."""
    service = accessory.add_service(ServicesTypes.CONTACT_SENSOR)

    cur_state = service.add_char(CharacteristicsTypes.CONTACT_STATE)
    cur_state.value = 0


async def test_contact_sensor_read_state(hass: HomeAssistant) -> None:
    """Test that we can read the state of a HomeKit contact accessory."""
    helper = await setup_test_component(hass, create_contact_sensor_service)

    await helper.async_update(
        ServicesTypes.CONTACT_SENSOR, {CharacteristicsTypes.CONTACT_STATE: 0}
    )
    state = await helper.poll_and_get_state()
    assert state.state == "off"

    await helper.async_update(
        ServicesTypes.CONTACT_SENSOR, {CharacteristicsTypes.CONTACT_STATE: 1}
    )
    state = await helper.poll_and_get_state()
    assert state.state == "on"

    assert state.attributes["device_class"] == BinarySensorDeviceClass.OPENING


def create_smoke_sensor_service(accessory):
    """Define smoke sensor characteristics."""
    service = accessory.add_service(ServicesTypes.SMOKE_SENSOR)

    cur_state = service.add_char(CharacteristicsTypes.SMOKE_DETECTED)
    cur_state.value = 0


async def test_smoke_sensor_read_state(hass: HomeAssistant) -> None:
    """Test that we can read the state of a HomeKit contact accessory."""
    helper = await setup_test_component(hass, create_smoke_sensor_service)

    await helper.async_update(
        ServicesTypes.SMOKE_SENSOR, {CharacteristicsTypes.SMOKE_DETECTED: 0}
    )
    state = await helper.poll_and_get_state()
    assert state.state == "off"

    await helper.async_update(
        ServicesTypes.SMOKE_SENSOR, {CharacteristicsTypes.SMOKE_DETECTED: 1}
    )
    state = await helper.poll_and_get_state()
    assert state.state == "on"

    assert state.attributes["device_class"] == BinarySensorDeviceClass.SMOKE


def create_carbon_monoxide_sensor_service(accessory):
    """Define carbon monoxide sensor characteristics."""
    service = accessory.add_service(ServicesTypes.CARBON_MONOXIDE_SENSOR)

    cur_state = service.add_char(CharacteristicsTypes.CARBON_MONOXIDE_DETECTED)
    cur_state.value = 0


async def test_carbon_monoxide_sensor_read_state(hass: HomeAssistant) -> None:
    """Test that we can read the state of a HomeKit contact accessory."""
    helper = await setup_test_component(hass, create_carbon_monoxide_sensor_service)

    await helper.async_update(
        ServicesTypes.CARBON_MONOXIDE_SENSOR,
        {CharacteristicsTypes.CARBON_MONOXIDE_DETECTED: 0},
    )
    state = await helper.poll_and_get_state()
    assert state.state == "off"

    await helper.async_update(
        ServicesTypes.CARBON_MONOXIDE_SENSOR,
        {CharacteristicsTypes.CARBON_MONOXIDE_DETECTED: 1},
    )
    state = await helper.poll_and_get_state()
    assert state.state == "on"

    assert state.attributes["device_class"] == BinarySensorDeviceClass.CO


def create_occupancy_sensor_service(accessory):
    """Define occupancy characteristics."""
    service = accessory.add_service(ServicesTypes.OCCUPANCY_SENSOR)

    cur_state = service.add_char(CharacteristicsTypes.OCCUPANCY_DETECTED)
    cur_state.value = 0


async def test_occupancy_sensor_read_state(hass: HomeAssistant) -> None:
    """Test that we can read the state of a HomeKit occupancy sensor accessory."""
    helper = await setup_test_component(hass, create_occupancy_sensor_service)

    await helper.async_update(
        ServicesTypes.OCCUPANCY_SENSOR, {CharacteristicsTypes.OCCUPANCY_DETECTED: False}
    )
    state = await helper.poll_and_get_state()
    assert state.state == "off"

    await helper.async_update(
        ServicesTypes.OCCUPANCY_SENSOR, {CharacteristicsTypes.OCCUPANCY_DETECTED: True}
    )
    state = await helper.poll_and_get_state()
    assert state.state == "on"

    assert state.attributes["device_class"] == BinarySensorDeviceClass.OCCUPANCY


def create_leak_sensor_service(accessory):
    """Define leak characteristics."""
    service = accessory.add_service(ServicesTypes.LEAK_SENSOR)

    cur_state = service.add_char(CharacteristicsTypes.LEAK_DETECTED)
    cur_state.value = 0


async def test_leak_sensor_read_state(hass: HomeAssistant) -> None:
    """Test that we can read the state of a HomeKit leak sensor accessory."""
    helper = await setup_test_component(hass, create_leak_sensor_service)

    await helper.async_update(
        ServicesTypes.LEAK_SENSOR, {CharacteristicsTypes.LEAK_DETECTED: 0}
    )
    state = await helper.poll_and_get_state()
    assert state.state == "off"

    await helper.async_update(
        ServicesTypes.LEAK_SENSOR, {CharacteristicsTypes.LEAK_DETECTED: 1}
    )
    state = await helper.poll_and_get_state()
    assert state.state == "on"

    assert state.attributes["device_class"] == BinarySensorDeviceClass.MOISTURE


async def test_migrate_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a we can migrate a binary_sensor unique id."""
    aid = get_next_aid()
    binary_sensor_entry = entity_registry.async_get_or_create(
        "binary_sensor",
        "homekit_controller",
        f"homekit-00:00:00:00:00:00-{aid}-8",
    )
    await setup_test_component(hass, create_leak_sensor_service)

    assert (
        entity_registry.async_get(binary_sensor_entry.entity_id).unique_id
        == f"00:00:00:00:00:00_{aid}_8"
    )
