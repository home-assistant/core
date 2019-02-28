"""
Test for the SmartThings climate platform.

The only mocking required is of the underlying SmartThings API object so
real HTTP calls are not initiated during testing.
"""
from pysmartthings import Attribute, Capability
from pysmartthings.device import Status
import pytest

from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY, ATTR_CURRENT_TEMPERATURE, ATTR_FAN_LIST,
    ATTR_FAN_MODE, ATTR_OPERATION_LIST, ATTR_OPERATION_MODE,
    ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW, DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE, SERVICE_SET_OPERATION_MODE, SERVICE_SET_TEMPERATURE,
    STATE_AUTO, STATE_COOL, STATE_ECO, STATE_HEAT, STATE_OFF, SUPPORT_FAN_MODE,
    SUPPORT_OPERATION_MODE, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_HIGH, SUPPORT_TARGET_TEMPERATURE_LOW)
from homeassistant.components.smartthings import climate
from homeassistant.components.smartthings.const import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES, ATTR_TEMPERATURE, STATE_UNKNOWN)

from .conftest import setup_platform


@pytest.fixture(name="legacy_thermostat")
def legacy_thermostat_fixture(device_factory):
    """Fixture returns a legacy thermostat."""
    device = device_factory(
        "Legacy Thermostat",
        capabilities=[Capability.thermostat],
        status={
            Attribute.cooling_setpoint: 74,
            Attribute.heating_setpoint: 68,
            Attribute.thermostat_fan_mode: 'auto',
            Attribute.supported_thermostat_fan_modes: ['auto', 'on'],
            Attribute.thermostat_mode: 'auto',
            Attribute.supported_thermostat_modes: climate.MODE_TO_STATE.keys(),
            Attribute.thermostat_operating_state: 'idle'
        }
    )
    device.status.attributes[Attribute.temperature] = Status(70, 'F', None)
    return device


@pytest.fixture(name="basic_thermostat")
def basic_thermostat_fixture(device_factory):
    """Fixture returns a basic thermostat."""
    device = device_factory(
        "Basic Thermostat",
        capabilities=[
            Capability.temperature_measurement,
            Capability.thermostat_cooling_setpoint,
            Capability.thermostat_heating_setpoint,
            Capability.thermostat_mode],
        status={
            Attribute.cooling_setpoint: 74,
            Attribute.heating_setpoint: 68,
            Attribute.thermostat_mode: 'off',
            Attribute.supported_thermostat_modes:
                ['off', 'auto', 'heat', 'cool']
        }
    )
    device.status.attributes[Attribute.temperature] = Status(70, 'F', None)
    return device


@pytest.fixture(name="thermostat")
def thermostat_fixture(device_factory):
    """Fixture returns a fully-featured thermostat."""
    device = device_factory(
        "Thermostat",
        capabilities=[
            Capability.temperature_measurement,
            Capability.relative_humidity_measurement,
            Capability.thermostat_cooling_setpoint,
            Capability.thermostat_heating_setpoint,
            Capability.thermostat_mode,
            Capability.thermostat_operating_state,
            Capability.thermostat_fan_mode],
        status={
            Attribute.cooling_setpoint: 74,
            Attribute.heating_setpoint: 68,
            Attribute.thermostat_fan_mode: 'on',
            Attribute.supported_thermostat_fan_modes: ['auto', 'on'],
            Attribute.thermostat_mode: 'heat',
            Attribute.supported_thermostat_modes:
                ['auto', 'heat', 'cool', 'off', 'eco'],
            Attribute.thermostat_operating_state: 'fan only',
            Attribute.humidity: 34
        }
    )
    device.status.attributes[Attribute.temperature] = Status(70, 'F', None)
    return device


@pytest.fixture(name="buggy_thermostat")
def buggy_thermostat_fixture(device_factory):
    """Fixture returns a buggy thermostat."""
    device = device_factory(
        "Buggy Thermostat",
        capabilities=[
            Capability.temperature_measurement,
            Capability.thermostat_cooling_setpoint,
            Capability.thermostat_heating_setpoint,
            Capability.thermostat_mode],
        status={
            Attribute.thermostat_mode: 'heating',
            Attribute.cooling_setpoint: 74,
            Attribute.heating_setpoint: 68}
    )
    device.status.attributes[Attribute.temperature] = Status(70, 'F', None)
    return device


async def test_async_setup_platform():
    """Test setup platform does nothing (it uses config entries)."""
    await climate.async_setup_platform(None, None, None)


async def test_legacy_thermostat_entity_state(hass, legacy_thermostat):
    """Tests the state attributes properly match the thermostat type."""
    await setup_platform(hass, CLIMATE_DOMAIN, legacy_thermostat)
    state = hass.states.get('climate.legacy_thermostat')
    assert state.state == STATE_AUTO
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == \
        SUPPORT_OPERATION_MODE | SUPPORT_FAN_MODE | \
        SUPPORT_TARGET_TEMPERATURE_HIGH | SUPPORT_TARGET_TEMPERATURE_LOW | \
        SUPPORT_TARGET_TEMPERATURE
    assert state.attributes[climate.ATTR_OPERATION_STATE] == 'idle'
    assert state.attributes[ATTR_OPERATION_LIST] == {
        STATE_AUTO, STATE_COOL, STATE_ECO, STATE_HEAT, STATE_OFF}
    assert state.attributes[ATTR_FAN_MODE] == 'auto'
    assert state.attributes[ATTR_FAN_LIST] == ['auto', 'on']
    assert state.attributes[ATTR_TARGET_TEMP_LOW] == 20  # celsius
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] == 23.3  # celsius
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 21.1  # celsius


async def test_basic_thermostat_entity_state(hass, basic_thermostat):
    """Tests the state attributes properly match the thermostat type."""
    await setup_platform(hass, CLIMATE_DOMAIN, basic_thermostat)
    state = hass.states.get('climate.basic_thermostat')
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == \
        SUPPORT_OPERATION_MODE | SUPPORT_TARGET_TEMPERATURE_HIGH | \
        SUPPORT_TARGET_TEMPERATURE_LOW | SUPPORT_TARGET_TEMPERATURE
    assert state.attributes[climate.ATTR_OPERATION_STATE] is None
    assert state.attributes[ATTR_OPERATION_LIST] == {
        STATE_OFF, STATE_AUTO, STATE_HEAT, STATE_COOL}
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 21.1  # celsius


async def test_thermostat_entity_state(hass, thermostat):
    """Tests the state attributes properly match the thermostat type."""
    await setup_platform(hass, CLIMATE_DOMAIN, thermostat)
    state = hass.states.get('climate.thermostat')
    assert state.state == STATE_HEAT
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == \
        SUPPORT_OPERATION_MODE | SUPPORT_FAN_MODE | \
        SUPPORT_TARGET_TEMPERATURE_HIGH | SUPPORT_TARGET_TEMPERATURE_LOW | \
        SUPPORT_TARGET_TEMPERATURE
    assert state.attributes[climate.ATTR_OPERATION_STATE] == 'fan only'
    assert state.attributes[ATTR_OPERATION_LIST] == {
        STATE_AUTO, STATE_HEAT, STATE_COOL, STATE_OFF, STATE_ECO}
    assert state.attributes[ATTR_FAN_MODE] == 'on'
    assert state.attributes[ATTR_FAN_LIST] == ['auto', 'on']
    assert state.attributes[ATTR_TEMPERATURE] == 20  # celsius
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 21.1  # celsius
    assert state.attributes[ATTR_CURRENT_HUMIDITY] == 34


async def test_buggy_thermostat_entity_state(hass, buggy_thermostat):
    """Tests the state attributes properly match the thermostat type."""
    await setup_platform(hass, CLIMATE_DOMAIN, buggy_thermostat)
    state = hass.states.get('climate.buggy_thermostat')
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == \
        SUPPORT_OPERATION_MODE | SUPPORT_TARGET_TEMPERATURE_HIGH | \
        SUPPORT_TARGET_TEMPERATURE_LOW | SUPPORT_TARGET_TEMPERATURE
    assert ATTR_OPERATION_LIST not in state.attributes
    assert state.attributes[ATTR_TEMPERATURE] is None
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 21.1  # celsius


async def test_buggy_thermostat_invalid_mode(hass, buggy_thermostat):
    """Tests when an invalid operation mode is included."""
    buggy_thermostat.status.update_attribute_value(
        Attribute.supported_thermostat_modes,
        ['heat', 'emergency heat', 'other'])
    await setup_platform(hass, CLIMATE_DOMAIN, buggy_thermostat)
    state = hass.states.get('climate.buggy_thermostat')
    assert state.attributes[ATTR_OPERATION_LIST] == {'heat'}


async def test_set_fan_mode(hass, thermostat):
    """Test the fan mode is set successfully."""
    await setup_platform(hass, CLIMATE_DOMAIN, thermostat)
    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_SET_FAN_MODE, {
            ATTR_ENTITY_ID: 'climate.thermostat',
            ATTR_FAN_MODE: 'auto'},
        blocking=True)
    state = hass.states.get('climate.thermostat')
    assert state.attributes[ATTR_FAN_MODE] == 'auto'


async def test_set_operation_mode(hass, thermostat):
    """Test the operation mode is set successfully."""
    await setup_platform(hass, CLIMATE_DOMAIN, thermostat)
    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_SET_OPERATION_MODE, {
            ATTR_ENTITY_ID: 'climate.thermostat',
            ATTR_OPERATION_MODE: STATE_ECO},
        blocking=True)
    state = hass.states.get('climate.thermostat')
    assert state.state == STATE_ECO


async def test_set_temperature_heat_mode(hass, thermostat):
    """Test the temperature is set successfully when in heat mode."""
    thermostat.status.thermostat_mode = 'heat'
    await setup_platform(hass, CLIMATE_DOMAIN, thermostat)
    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_SET_TEMPERATURE, {
            ATTR_ENTITY_ID: 'climate.thermostat',
            ATTR_TEMPERATURE: 21},
        blocking=True)
    state = hass.states.get('climate.thermostat')
    assert state.attributes[ATTR_OPERATION_MODE] == STATE_HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 21
    assert thermostat.status.heating_setpoint == 69.8


async def test_set_temperature_cool_mode(hass, thermostat):
    """Test the temperature is set successfully when in cool mode."""
    thermostat.status.thermostat_mode = 'cool'
    await setup_platform(hass, CLIMATE_DOMAIN, thermostat)
    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_SET_TEMPERATURE, {
            ATTR_ENTITY_ID: 'climate.thermostat',
            ATTR_TEMPERATURE: 21},
        blocking=True)
    state = hass.states.get('climate.thermostat')
    assert state.attributes[ATTR_TEMPERATURE] == 21


async def test_set_temperature(hass, thermostat):
    """Test the temperature is set successfully."""
    thermostat.status.thermostat_mode = 'auto'
    await setup_platform(hass, CLIMATE_DOMAIN, thermostat)
    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_SET_TEMPERATURE, {
            ATTR_ENTITY_ID: 'climate.thermostat',
            ATTR_TARGET_TEMP_HIGH: 25.5,
            ATTR_TARGET_TEMP_LOW: 22.2},
        blocking=True)
    state = hass.states.get('climate.thermostat')
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] == 25.5
    assert state.attributes[ATTR_TARGET_TEMP_LOW] == 22.2


async def test_set_temperature_with_mode(hass, thermostat):
    """Test the temperature and mode is set successfully."""
    await setup_platform(hass, CLIMATE_DOMAIN, thermostat)
    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_SET_TEMPERATURE, {
            ATTR_ENTITY_ID: 'climate.thermostat',
            ATTR_TARGET_TEMP_HIGH: 25.5,
            ATTR_TARGET_TEMP_LOW: 22.2,
            ATTR_OPERATION_MODE: STATE_AUTO},
        blocking=True)
    state = hass.states.get('climate.thermostat')
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] == 25.5
    assert state.attributes[ATTR_TARGET_TEMP_LOW] == 22.2
    assert state.state == STATE_AUTO


async def test_entity_and_device_attributes(hass, thermostat):
    """Test the attributes of the entries are correct."""
    await setup_platform(hass, CLIMATE_DOMAIN, thermostat)
    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    device_registry = await hass.helpers.device_registry.async_get_registry()

    entry = entity_registry.async_get("climate.thermostat")
    assert entry
    assert entry.unique_id == thermostat.device_id

    entry = device_registry.async_get_device(
        {(DOMAIN, thermostat.device_id)}, [])
    assert entry
    assert entry.name == thermostat.label
    assert entry.model == thermostat.device_type_name
    assert entry.manufacturer == 'Unavailable'
