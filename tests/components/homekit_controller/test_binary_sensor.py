"""Basic checks for HomeKit motion sensors and contact sensors."""

from collections.abc import Callable

from aiohomekit.model import Accessory
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import Service, ServicesTypes

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import Helper, setup_test_accessories, setup_test_component


def create_motion_sensor_service(accessory: Accessory) -> None:
    """Define motion characteristics as per page 225 of HAP spec."""
    service = accessory.add_service(ServicesTypes.MOTION_SENSOR)

    cur_state = service.add_char(CharacteristicsTypes.MOTION_DETECTED)
    cur_state.value = 0


async def test_motion_sensor_read_state(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that we can read the state of a HomeKit motion sensor accessory."""
    helper = await setup_test_component(
        hass, get_next_aid(), create_motion_sensor_service
    )

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


def create_contact_sensor_service(accessory: Accessory) -> None:
    """Define contact characteristics."""
    service = accessory.add_service(ServicesTypes.CONTACT_SENSOR)

    cur_state = service.add_char(CharacteristicsTypes.CONTACT_STATE)
    cur_state.value = 0


async def test_contact_sensor_read_state(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that we can read the state of a HomeKit contact accessory."""
    helper = await setup_test_component(
        hass, get_next_aid(), create_contact_sensor_service
    )

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


def create_smoke_sensor_service(accessory: Accessory) -> None:
    """Define smoke sensor characteristics."""
    service = accessory.add_service(ServicesTypes.SMOKE_SENSOR)

    cur_state = service.add_char(CharacteristicsTypes.SMOKE_DETECTED)
    cur_state.value = 0


async def test_smoke_sensor_read_state(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that we can read the state of a HomeKit contact accessory."""
    helper = await setup_test_component(
        hass, get_next_aid(), create_smoke_sensor_service
    )

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


def create_carbon_monoxide_sensor_service(accessory: Accessory) -> None:
    """Define carbon monoxide sensor characteristics."""
    service = accessory.add_service(ServicesTypes.CARBON_MONOXIDE_SENSOR)

    cur_state = service.add_char(CharacteristicsTypes.CARBON_MONOXIDE_DETECTED)
    cur_state.value = 0


async def test_carbon_monoxide_sensor_read_state(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that we can read the state of a HomeKit contact accessory."""
    helper = await setup_test_component(
        hass, get_next_aid(), create_carbon_monoxide_sensor_service
    )

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


def create_occupancy_sensor_service(accessory: Accessory) -> None:
    """Define occupancy characteristics."""
    service = accessory.add_service(ServicesTypes.OCCUPANCY_SENSOR)

    cur_state = service.add_char(CharacteristicsTypes.OCCUPANCY_DETECTED)
    cur_state.value = 0


async def test_occupancy_sensor_read_state(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that we can read the state of a HomeKit occupancy sensor accessory."""
    helper = await setup_test_component(
        hass, get_next_aid(), create_occupancy_sensor_service
    )

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


def create_leak_sensor_service(accessory: Accessory) -> None:
    """Define leak characteristics."""
    service = accessory.add_service(ServicesTypes.LEAK_SENSOR)

    cur_state = service.add_char(CharacteristicsTypes.LEAK_DETECTED)
    cur_state.value = 0


def create_valve_with_status_characteristics(accessory: Accessory) -> Service:
    """Define valve characteristics with status binary sensors."""
    service = accessory.add_service(ServicesTypes.VALVE, name="TestDevice")

    active = service.add_char(CharacteristicsTypes.ACTIVE)
    active.value = False

    low_battery = service.add_char(CharacteristicsTypes.STATUS_LO_BATT)
    low_battery.value = 0

    fault = service.add_char(CharacteristicsTypes.STATUS_FAULT)
    fault.value = 0

    return service


def create_sensor_with_duplicate_low_battery_characteristics(
    accessory: Accessory,
) -> None:
    """Define sensor services that repeat the same low battery status."""
    for service_type, characteristic_type in (
        (ServicesTypes.TEMPERATURE_SENSOR, CharacteristicsTypes.TEMPERATURE_CURRENT),
        (
            ServicesTypes.HUMIDITY_SENSOR,
            CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT,
        ),
    ):
        service = accessory.add_service(service_type, name="Shared Sensor")

        current = service.add_char(characteristic_type)
        current.value = 0

        low_battery = service.add_char(CharacteristicsTypes.STATUS_LO_BATT)
        low_battery.value = 0


def create_sensor_with_unnamed_low_battery_characteristics(
    accessory: Accessory,
) -> None:
    """Define unnamed sensor services that repeat the same low battery status."""
    for service_type, characteristic_type in (
        (ServicesTypes.TEMPERATURE_SENSOR, CharacteristicsTypes.TEMPERATURE_CURRENT),
        (
            ServicesTypes.HUMIDITY_SENSOR,
            CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT,
        ),
    ):
        service = accessory.add_service(service_type)

        current = service.add_char(characteristic_type)
        current.value = 0

        low_battery = service.add_char(CharacteristicsTypes.STATUS_LO_BATT)
        low_battery.value = 0


def create_sensor_with_named_low_battery_characteristic(accessory: Accessory) -> None:
    """Define a named sensor service with low battery status."""
    service = accessory.add_service(
        ServicesTypes.TEMPERATURE_SENSOR, name="Temperature"
    )

    current = service.add_char(CharacteristicsTypes.TEMPERATURE_CURRENT)
    current.value = 0

    low_battery = service.add_char(CharacteristicsTypes.STATUS_LO_BATT)
    low_battery.value = 0


def create_labeled_valves_with_low_battery_characteristics(
    accessory: Accessory,
) -> None:
    """Define labeled valve services with low battery status."""
    for label_index in (1.0, 2.0):
        service = accessory.add_service(ServicesTypes.VALVE)

        service_label_index = service.add_char(CharacteristicsTypes.SERVICE_LABEL_INDEX)
        service_label_index.value = label_index

        active = service.add_char(CharacteristicsTypes.ACTIVE)
        active.value = False

        low_battery = service.add_char(CharacteristicsTypes.STATUS_LO_BATT)
        low_battery.value = 0


def create_sensor_with_battery_service(accessory: Accessory) -> None:
    """Define a sensor with its own battery service."""
    service = accessory.add_service(
        ServicesTypes.TEMPERATURE_SENSOR, name="Temperature"
    )

    current = service.add_char(CharacteristicsTypes.TEMPERATURE_CURRENT)
    current.value = 0

    low_battery = service.add_char(CharacteristicsTypes.STATUS_LO_BATT)
    low_battery.value = 0

    battery = accessory.add_service(ServicesTypes.BATTERY_SERVICE, name="Battery")
    battery_level = battery.add_char(CharacteristicsTypes.BATTERY_LEVEL)
    battery_level.value = 100

    battery_low = battery.add_char(CharacteristicsTypes.STATUS_LO_BATT)
    battery_low.value = 0


async def test_leak_sensor_read_state(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that we can read the state of a HomeKit leak sensor accessory."""
    helper = await setup_test_component(
        hass, get_next_aid(), create_leak_sensor_service
    )

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


async def test_valve_status_binary_sensors(
    hass: HomeAssistant,
    get_next_aid: Callable[[], int],
) -> None:
    """Test valve status characteristics are exposed as binary sensors."""
    helper = await setup_test_component(
        hass, get_next_aid(), create_valve_with_status_characteristics
    )

    low_battery = Helper(
        hass,
        "binary_sensor.testdevice_battery",
        helper.pairing,
        helper.accessory,
        helper.config_entry,
    )
    fault = Helper(
        hass,
        "binary_sensor.testdevice_problem",
        helper.pairing,
        helper.accessory,
        helper.config_entry,
    )

    state = await low_battery.poll_and_get_state()
    assert state.state == "off"
    assert state.attributes["device_class"] == BinarySensorDeviceClass.BATTERY

    state = await low_battery.async_update(
        ServicesTypes.VALVE,
        {CharacteristicsTypes.STATUS_LO_BATT: 1},
    )
    assert state.state == "on"

    state = await fault.poll_and_get_state()
    assert state.state == "off"
    assert state.attributes["device_class"] == BinarySensorDeviceClass.PROBLEM

    state = await fault.async_update(
        ServicesTypes.VALVE,
        {CharacteristicsTypes.STATUS_FAULT: 1},
    )
    assert state.state == "on"


async def test_duplicate_low_battery_characteristics_create_single_binary_sensor(
    hass: HomeAssistant,
    get_next_aid: Callable[[], int],
) -> None:
    """Test repeated low battery characteristics on one sensor create one entity."""
    accessory = Accessory.create_with_info(
        get_next_aid(), "Shared Sensor", "example.com", "Test", "0001", "0.1"
    )
    create_sensor_with_duplicate_low_battery_characteristics(accessory)

    await setup_test_accessories(hass, [accessory])

    low_battery = hass.states.get("binary_sensor.shared_sensor_battery")
    assert low_battery
    assert hass.states.get("binary_sensor.shared_sensor_battery_2") is None


async def test_unnamed_low_battery_characteristics_create_single_binary_sensor(
    hass: HomeAssistant,
    get_next_aid: Callable[[], int],
) -> None:
    """Test unnamed low battery characteristics on one sensor create one entity."""
    accessory = Accessory.create_with_info(
        get_next_aid(), "Unnamed Sensor", "example.com", "Test", "0001", "0.1"
    )
    create_sensor_with_unnamed_low_battery_characteristics(accessory)

    await setup_test_accessories(hass, [accessory])

    low_battery = hass.states.get("binary_sensor.unnamed_sensor_battery")
    assert low_battery
    assert hass.states.get("binary_sensor.unnamed_sensor_battery_2") is None


async def test_named_low_battery_characteristic_creates_binary_sensor(
    hass: HomeAssistant,
    get_next_aid: Callable[[], int],
) -> None:
    """Test low battery characteristics on named services create an entity."""
    accessory = Accessory.create_with_info(
        get_next_aid(), "Outdoor Sensor", "example.com", "Test", "0001", "0.1"
    )
    create_sensor_with_named_low_battery_characteristic(accessory)

    await setup_test_accessories(hass, [accessory])

    low_battery = hass.states.get("binary_sensor.outdoor_sensor_temperature_battery")
    assert low_battery


async def test_labeled_low_battery_characteristics_create_scoped_binary_sensors(
    hass: HomeAssistant,
    get_next_aid: Callable[[], int],
) -> None:
    """Test low battery characteristics on labeled services create entities."""
    await setup_test_component(
        hass, get_next_aid(), create_labeled_valves_with_low_battery_characteristics
    )

    valve_1 = hass.states.get("binary_sensor.testdevice_valve_1_battery")
    assert valve_1

    valve_2 = hass.states.get("binary_sensor.testdevice_valve_2_battery")
    assert valve_2


async def test_low_battery_characteristic_ignored_with_battery_service(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test low battery characteristics are ignored when a battery service exists."""
    accessory = Accessory.create_with_info(
        get_next_aid(), "Outdoor Sensor", "example.com", "Test", "0001", "0.1"
    )
    create_sensor_with_battery_service(accessory)

    await setup_test_accessories(hass, [accessory])

    assert hass.states.get("sensor.outdoor_sensor_battery")
    assert hass.states.get("binary_sensor.outdoor_sensor_battery") is None
    assert hass.states.get("binary_sensor.outdoor_sensor_temperature_battery") is None


async def test_migrate_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    get_next_aid: Callable[[], int],
) -> None:
    """Test a we can migrate a binary_sensor unique id."""
    aid = get_next_aid()
    binary_sensor_entry = entity_registry.async_get_or_create(
        "binary_sensor",
        "homekit_controller",
        f"homekit-00:00:00:00:00:00-{aid}-8",
    )
    await setup_test_component(hass, aid, create_leak_sensor_service)

    assert (
        entity_registry.async_get(binary_sensor_entry.entity_id).unique_id
        == f"00:00:00:00:00:00_{aid}_8"
    )
