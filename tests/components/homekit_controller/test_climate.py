"""Basic checks for HomeKitclimate."""
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes

from homeassistant.components.climate.const import (
    DOMAIN,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
)

from tests.components.homekit_controller.common import setup_test_component

HEATING_COOLING_TARGET = ("thermostat", "heating-cooling.target")
HEATING_COOLING_CURRENT = ("thermostat", "heating-cooling.current")
TEMPERATURE_TARGET = ("thermostat", "temperature.target")
TEMPERATURE_CURRENT = ("thermostat", "temperature.current")
HUMIDITY_TARGET = ("thermostat", "relative-humidity.target")
HUMIDITY_CURRENT = ("thermostat", "relative-humidity.current")


def create_thermostat_service(accessory):
    """Define thermostat characteristics."""
    service = accessory.add_service(ServicesTypes.THERMOSTAT)

    char = service.add_char(CharacteristicsTypes.HEATING_COOLING_TARGET)
    char.value = 0

    char = service.add_char(CharacteristicsTypes.HEATING_COOLING_CURRENT)
    char.value = 0

    char = service.add_char(CharacteristicsTypes.TEMPERATURE_TARGET)
    char.minValue = 7
    char.maxValue = 35
    char.value = 0

    char = service.add_char(CharacteristicsTypes.TEMPERATURE_CURRENT)
    char.value = 0

    char = service.add_char(CharacteristicsTypes.RELATIVE_HUMIDITY_TARGET)
    char.value = 0

    char = service.add_char(CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT)
    char.value = 0


def create_thermostat_service_min_max(accessory):
    """Define thermostat characteristics."""
    service = accessory.add_service(ServicesTypes.THERMOSTAT)
    char = service.add_char(CharacteristicsTypes.HEATING_COOLING_TARGET)
    char.value = 0
    char.minValue = 0
    char.maxValue = 1


async def test_climate_respect_supported_op_modes_1(hass, utcnow):
    """Test that climate respects minValue/maxValue hints."""
    helper = await setup_test_component(hass, create_thermostat_service_min_max)
    state = await helper.poll_and_get_state()
    assert state.attributes["hvac_modes"] == ["off", "heat"]


def create_thermostat_service_valid_vals(accessory):
    """Define thermostat characteristics."""
    service = accessory.add_service(ServicesTypes.THERMOSTAT)
    char = service.add_char(CharacteristicsTypes.HEATING_COOLING_TARGET)
    char.value = 0
    char.valid_values = [0, 1, 2]


async def test_climate_respect_supported_op_modes_2(hass, utcnow):
    """Test that climate respects validValue hints."""
    helper = await setup_test_component(hass, create_thermostat_service_valid_vals)
    state = await helper.poll_and_get_state()
    assert state.attributes["hvac_modes"] == ["off", "heat", "cool"]


async def test_climate_change_thermostat_state(hass, utcnow):
    """Test that we can turn a HomeKit thermostat on and off again."""
    helper = await setup_test_component(hass, create_thermostat_service)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {"entity_id": "climate.testdevice", "hvac_mode": HVAC_MODE_HEAT},
        blocking=True,
    )

    assert helper.characteristics[HEATING_COOLING_TARGET].value == 1

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {"entity_id": "climate.testdevice", "hvac_mode": HVAC_MODE_COOL},
        blocking=True,
    )
    assert helper.characteristics[HEATING_COOLING_TARGET].value == 2

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {"entity_id": "climate.testdevice", "hvac_mode": HVAC_MODE_HEAT_COOL},
        blocking=True,
    )
    assert helper.characteristics[HEATING_COOLING_TARGET].value == 3

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {"entity_id": "climate.testdevice", "hvac_mode": HVAC_MODE_OFF},
        blocking=True,
    )
    assert helper.characteristics[HEATING_COOLING_TARGET].value == 0


async def test_climate_change_thermostat_temperature(hass, utcnow):
    """Test that we can turn a HomeKit thermostat on and off again."""
    helper = await setup_test_component(hass, create_thermostat_service)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {"entity_id": "climate.testdevice", "temperature": 21},
        blocking=True,
    )
    assert helper.characteristics[TEMPERATURE_TARGET].value == 21

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {"entity_id": "climate.testdevice", "temperature": 25},
        blocking=True,
    )
    assert helper.characteristics[TEMPERATURE_TARGET].value == 25


async def test_climate_change_thermostat_humidity(hass, utcnow):
    """Test that we can turn a HomeKit thermostat on and off again."""
    helper = await setup_test_component(hass, create_thermostat_service)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HUMIDITY,
        {"entity_id": "climate.testdevice", "humidity": 50},
        blocking=True,
    )
    assert helper.characteristics[HUMIDITY_TARGET].value == 50

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HUMIDITY,
        {"entity_id": "climate.testdevice", "humidity": 45},
        blocking=True,
    )
    assert helper.characteristics[HUMIDITY_TARGET].value == 45


async def test_climate_read_thermostat_state(hass, utcnow):
    """Test that we can read the state of a HomeKit thermostat accessory."""
    helper = await setup_test_component(hass, create_thermostat_service)

    # Simulate that heating is on
    helper.characteristics[TEMPERATURE_CURRENT].value = 19
    helper.characteristics[TEMPERATURE_TARGET].value = 21
    helper.characteristics[HEATING_COOLING_CURRENT].value = 1
    helper.characteristics[HEATING_COOLING_TARGET].value = 1
    helper.characteristics[HUMIDITY_CURRENT].value = 50
    helper.characteristics[HUMIDITY_TARGET].value = 45

    state = await helper.poll_and_get_state()
    assert state.state == HVAC_MODE_HEAT
    assert state.attributes["current_temperature"] == 19
    assert state.attributes["current_humidity"] == 50
    assert state.attributes["min_temp"] == 7
    assert state.attributes["max_temp"] == 35

    # Simulate that cooling is on
    helper.characteristics[TEMPERATURE_CURRENT].value = 21
    helper.characteristics[TEMPERATURE_TARGET].value = 19
    helper.characteristics[HEATING_COOLING_CURRENT].value = 2
    helper.characteristics[HEATING_COOLING_TARGET].value = 2
    helper.characteristics[HUMIDITY_CURRENT].value = 45
    helper.characteristics[HUMIDITY_TARGET].value = 45

    state = await helper.poll_and_get_state()
    assert state.state == HVAC_MODE_COOL
    assert state.attributes["current_temperature"] == 21
    assert state.attributes["current_humidity"] == 45

    # Simulate that we are in heat/cool mode
    helper.characteristics[TEMPERATURE_CURRENT].value = 21
    helper.characteristics[TEMPERATURE_TARGET].value = 21
    helper.characteristics[HEATING_COOLING_CURRENT].value = 0
    helper.characteristics[HEATING_COOLING_TARGET].value = 3

    state = await helper.poll_and_get_state()
    assert state.state == HVAC_MODE_HEAT_COOL


async def test_hvac_mode_vs_hvac_action(hass, utcnow):
    """Check that we haven't conflated hvac_mode and hvac_action."""
    helper = await setup_test_component(hass, create_thermostat_service)

    # Simulate that current temperature is above target temp
    # Heating might be on, but hvac_action currently 'off'
    helper.characteristics[TEMPERATURE_CURRENT].value = 22
    helper.characteristics[TEMPERATURE_TARGET].value = 21
    helper.characteristics[HEATING_COOLING_CURRENT].value = 0
    helper.characteristics[HEATING_COOLING_TARGET].value = 1
    helper.characteristics[HUMIDITY_CURRENT].value = 50
    helper.characteristics[HUMIDITY_TARGET].value = 45

    state = await helper.poll_and_get_state()
    assert state.state == "heat"
    assert state.attributes["hvac_action"] == "idle"

    # Simulate that current temperature is below target temp
    # Heating might be on and hvac_action currently 'heat'
    helper.characteristics[TEMPERATURE_CURRENT].value = 19
    helper.characteristics[HEATING_COOLING_CURRENT].value = 1

    state = await helper.poll_and_get_state()
    assert state.state == "heat"
    assert state.attributes["hvac_action"] == "heating"
