"""Basic checks for HomeKit sensor."""
from tests.components.homekit_controller.common import FakeService, setup_test_component

TEMPERATURE = ("temperature", "temperature.current")
HUMIDITY = ("humidity", "relative-humidity.current")
LIGHT_LEVEL = ("light", "light-level.current")
CARBON_DIOXIDE_LEVEL = ("carbon-dioxide", "carbon-dioxide.level")
BATTERY_LEVEL = ("battery", "battery-level")
CHARGING_STATE = ("battery", "charging-state")
LO_BATT = ("battery", "status-lo-batt")


def create_temperature_sensor_service():
    """Define temperature characteristics."""
    service = FakeService("public.hap.service.sensor.temperature")

    cur_state = service.add_characteristic("temperature.current")
    cur_state.value = 0

    return service


def create_humidity_sensor_service():
    """Define humidity characteristics."""
    service = FakeService("public.hap.service.sensor.humidity")

    cur_state = service.add_characteristic("relative-humidity.current")
    cur_state.value = 0

    return service


def create_light_level_sensor_service():
    """Define light level characteristics."""
    service = FakeService("public.hap.service.sensor.light")

    cur_state = service.add_characteristic("light-level.current")
    cur_state.value = 0

    return service


def create_carbon_dioxide_level_sensor_service():
    """Define carbon dioxide level characteristics."""
    service = FakeService("public.hap.service.sensor.carbon-dioxide")

    cur_state = service.add_characteristic("carbon-dioxide.level")
    cur_state.value = 0

    return service


def create_battery_level_sensor():
    """Define battery level characteristics."""
    service = FakeService("public.hap.service.battery")

    cur_state = service.add_characteristic("battery-level")
    cur_state.value = 100

    low_battery = service.add_characteristic("status-lo-batt")
    low_battery.value = 0

    charging_state = service.add_characteristic("charging-state")
    charging_state.value = 0

    return service


async def test_temperature_sensor_read_state(hass, utcnow):
    """Test reading the state of a HomeKit temperature sensor accessory."""
    sensor = create_temperature_sensor_service()
    helper = await setup_test_component(hass, [sensor], suffix="temperature")

    helper.characteristics[TEMPERATURE].value = 10
    state = await helper.poll_and_get_state()
    assert state.state == "10"

    helper.characteristics[TEMPERATURE].value = 20
    state = await helper.poll_and_get_state()
    assert state.state == "20"


async def test_humidity_sensor_read_state(hass, utcnow):
    """Test reading the state of a HomeKit humidity sensor accessory."""
    sensor = create_humidity_sensor_service()
    helper = await setup_test_component(hass, [sensor], suffix="humidity")

    helper.characteristics[HUMIDITY].value = 10
    state = await helper.poll_and_get_state()
    assert state.state == "10"

    helper.characteristics[HUMIDITY].value = 20
    state = await helper.poll_and_get_state()
    assert state.state == "20"


async def test_light_level_sensor_read_state(hass, utcnow):
    """Test reading the state of a HomeKit temperature sensor accessory."""
    sensor = create_light_level_sensor_service()
    helper = await setup_test_component(hass, [sensor], suffix="light_level")

    helper.characteristics[LIGHT_LEVEL].value = 10
    state = await helper.poll_and_get_state()
    assert state.state == "10"

    helper.characteristics[LIGHT_LEVEL].value = 20
    state = await helper.poll_and_get_state()
    assert state.state == "20"


async def test_carbon_dioxide_level_sensor_read_state(hass, utcnow):
    """Test reading the state of a HomeKit carbon dioxide sensor accessory."""
    sensor = create_carbon_dioxide_level_sensor_service()
    helper = await setup_test_component(hass, [sensor], suffix="co2")

    helper.characteristics[CARBON_DIOXIDE_LEVEL].value = 10
    state = await helper.poll_and_get_state()
    assert state.state == "10"

    helper.characteristics[CARBON_DIOXIDE_LEVEL].value = 20
    state = await helper.poll_and_get_state()
    assert state.state == "20"


async def test_battery_level_sensor(hass, utcnow):
    """Test reading the state of a HomeKit battery level sensor."""
    sensor = create_battery_level_sensor()
    helper = await setup_test_component(hass, [sensor], suffix="battery")

    helper.characteristics[BATTERY_LEVEL].value = 100
    state = await helper.poll_and_get_state()
    assert state.state == "100"
    assert state.attributes["icon"] == "mdi:battery"

    helper.characteristics[BATTERY_LEVEL].value = 20
    state = await helper.poll_and_get_state()
    assert state.state == "20"
    assert state.attributes["icon"] == "mdi:battery-20"


async def test_battery_charging(hass, utcnow):
    """Test reading the state of a HomeKit battery's charging state."""
    sensor = create_battery_level_sensor()
    helper = await setup_test_component(hass, [sensor], suffix="battery")

    helper.characteristics[BATTERY_LEVEL].value = 0
    helper.characteristics[CHARGING_STATE].value = 1
    state = await helper.poll_and_get_state()
    assert state.attributes["icon"] == "mdi:battery-outline"

    helper.characteristics[BATTERY_LEVEL].value = 20
    state = await helper.poll_and_get_state()
    assert state.attributes["icon"] == "mdi:battery-charging-20"


async def test_battery_low(hass, utcnow):
    """Test reading the state of a HomeKit battery's low state."""
    sensor = create_battery_level_sensor()
    helper = await setup_test_component(hass, [sensor], suffix="battery")

    helper.characteristics[LO_BATT].value = 0
    helper.characteristics[BATTERY_LEVEL].value = 1
    state = await helper.poll_and_get_state()
    assert state.attributes["icon"] == "mdi:battery-10"

    helper.characteristics[LO_BATT].value = 1
    state = await helper.poll_and_get_state()
    assert state.attributes["icon"] == "mdi:battery-alert"
