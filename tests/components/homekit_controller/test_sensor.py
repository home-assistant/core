"""Basic checks for HomeKit sensor."""
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_TEMPERATURE,
)

from tests.components.homekit_controller.common import Helper, setup_test_component

TEMPERATURE = ("temperature", "temperature.current")
HUMIDITY = ("humidity", "relative-humidity.current")
LIGHT_LEVEL = ("light", "light-level.current")
CARBON_DIOXIDE_LEVEL = ("carbon-dioxide", "carbon-dioxide.level")
BATTERY_LEVEL = ("battery", "battery-level")
CHARGING_STATE = ("battery", "charging-state")
LO_BATT = ("battery", "status-lo-batt")
ON = ("outlet", "on")


def create_temperature_sensor_service(accessory):
    """Define temperature characteristics."""
    service = accessory.add_service(ServicesTypes.TEMPERATURE_SENSOR)

    cur_state = service.add_char(CharacteristicsTypes.TEMPERATURE_CURRENT)
    cur_state.value = 0


def create_humidity_sensor_service(accessory):
    """Define humidity characteristics."""
    service = accessory.add_service(ServicesTypes.HUMIDITY_SENSOR)

    cur_state = service.add_char(CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT)
    cur_state.value = 0


def create_light_level_sensor_service(accessory):
    """Define light level characteristics."""
    service = accessory.add_service(ServicesTypes.LIGHT_SENSOR)

    cur_state = service.add_char(CharacteristicsTypes.LIGHT_LEVEL_CURRENT)
    cur_state.value = 0


def create_carbon_dioxide_level_sensor_service(accessory):
    """Define carbon dioxide level characteristics."""
    service = accessory.add_service(ServicesTypes.CARBON_DIOXIDE_SENSOR)

    cur_state = service.add_char(CharacteristicsTypes.CARBON_DIOXIDE_LEVEL)
    cur_state.value = 0


def create_battery_level_sensor(accessory):
    """Define battery level characteristics."""
    service = accessory.add_service(ServicesTypes.BATTERY_SERVICE)

    cur_state = service.add_char(CharacteristicsTypes.BATTERY_LEVEL)
    cur_state.value = 100

    low_battery = service.add_char(CharacteristicsTypes.STATUS_LO_BATT)
    low_battery.value = 0

    charging_state = service.add_char(CharacteristicsTypes.CHARGING_STATE)
    charging_state.value = 0

    return service


async def test_temperature_sensor_read_state(hass, utcnow):
    """Test reading the state of a HomeKit temperature sensor accessory."""
    helper = await setup_test_component(
        hass, create_temperature_sensor_service, suffix="temperature"
    )

    helper.characteristics[TEMPERATURE].value = 10
    state = await helper.poll_and_get_state()
    assert state.state == "10"

    helper.characteristics[TEMPERATURE].value = 20
    state = await helper.poll_and_get_state()
    assert state.state == "20"

    assert state.attributes["device_class"] == DEVICE_CLASS_TEMPERATURE


async def test_humidity_sensor_read_state(hass, utcnow):
    """Test reading the state of a HomeKit humidity sensor accessory."""
    helper = await setup_test_component(
        hass, create_humidity_sensor_service, suffix="humidity"
    )

    helper.characteristics[HUMIDITY].value = 10
    state = await helper.poll_and_get_state()
    assert state.state == "10"

    helper.characteristics[HUMIDITY].value = 20
    state = await helper.poll_and_get_state()
    assert state.state == "20"

    assert state.attributes["device_class"] == DEVICE_CLASS_HUMIDITY


async def test_light_level_sensor_read_state(hass, utcnow):
    """Test reading the state of a HomeKit temperature sensor accessory."""
    helper = await setup_test_component(
        hass, create_light_level_sensor_service, suffix="light_level"
    )

    helper.characteristics[LIGHT_LEVEL].value = 10
    state = await helper.poll_and_get_state()
    assert state.state == "10"

    helper.characteristics[LIGHT_LEVEL].value = 20
    state = await helper.poll_and_get_state()
    assert state.state == "20"

    assert state.attributes["device_class"] == DEVICE_CLASS_ILLUMINANCE


async def test_carbon_dioxide_level_sensor_read_state(hass, utcnow):
    """Test reading the state of a HomeKit carbon dioxide sensor accessory."""
    helper = await setup_test_component(
        hass, create_carbon_dioxide_level_sensor_service, suffix="co2"
    )

    helper.characteristics[CARBON_DIOXIDE_LEVEL].value = 10
    state = await helper.poll_and_get_state()
    assert state.state == "10"

    helper.characteristics[CARBON_DIOXIDE_LEVEL].value = 20
    state = await helper.poll_and_get_state()
    assert state.state == "20"


async def test_battery_level_sensor(hass, utcnow):
    """Test reading the state of a HomeKit battery level sensor."""
    helper = await setup_test_component(
        hass, create_battery_level_sensor, suffix="battery"
    )

    helper.characteristics[BATTERY_LEVEL].value = 100
    state = await helper.poll_and_get_state()
    assert state.state == "100"
    assert state.attributes["icon"] == "mdi:battery"

    helper.characteristics[BATTERY_LEVEL].value = 20
    state = await helper.poll_and_get_state()
    assert state.state == "20"
    assert state.attributes["icon"] == "mdi:battery-20"

    assert state.attributes["device_class"] == DEVICE_CLASS_BATTERY


async def test_battery_charging(hass, utcnow):
    """Test reading the state of a HomeKit battery's charging state."""
    helper = await setup_test_component(
        hass, create_battery_level_sensor, suffix="battery"
    )

    helper.characteristics[BATTERY_LEVEL].value = 0
    helper.characteristics[CHARGING_STATE].value = 1
    state = await helper.poll_and_get_state()
    assert state.attributes["icon"] == "mdi:battery-outline"

    helper.characteristics[BATTERY_LEVEL].value = 20
    state = await helper.poll_and_get_state()
    assert state.attributes["icon"] == "mdi:battery-charging-20"


async def test_battery_low(hass, utcnow):
    """Test reading the state of a HomeKit battery's low state."""
    helper = await setup_test_component(
        hass, create_battery_level_sensor, suffix="battery"
    )

    helper.characteristics[LO_BATT].value = 0
    helper.characteristics[BATTERY_LEVEL].value = 1
    state = await helper.poll_and_get_state()
    assert state.attributes["icon"] == "mdi:battery-10"

    helper.characteristics[LO_BATT].value = 1
    state = await helper.poll_and_get_state()
    assert state.attributes["icon"] == "mdi:battery-alert"


def create_switch_with_sensor(accessory):
    """Define battery level characteristics."""
    service = accessory.add_service(ServicesTypes.OUTLET)

    realtime_energy = service.add_char(
        CharacteristicsTypes.Vendor.KOOGEEK_REALTIME_ENERGY
    )
    realtime_energy.value = 0
    realtime_energy.format = "float"

    cur_state = service.add_char(CharacteristicsTypes.ON)
    cur_state.value = True

    return service


async def test_switch_with_sensor(hass, utcnow):
    """Test a switch service that has a sensor characteristic is correctly handled."""
    helper = await setup_test_component(hass, create_switch_with_sensor)
    outlet = helper.accessory.services.first(service_type=ServicesTypes.OUTLET)

    # Helper will be for the primary entity, which is the outlet. Make a helper for the sensor.
    energy_helper = Helper(
        hass,
        "sensor.testdevice_real_time_energy",
        helper.pairing,
        helper.accessory,
        helper.config_entry,
    )

    outlet = energy_helper.accessory.services.first(service_type=ServicesTypes.OUTLET)
    realtime_energy = outlet[CharacteristicsTypes.Vendor.KOOGEEK_REALTIME_ENERGY]

    realtime_energy.value = 1
    state = await energy_helper.poll_and_get_state()
    assert state.state == "1"

    realtime_energy.value = 50
    state = await energy_helper.poll_and_get_state()
    assert state.state == "50"
