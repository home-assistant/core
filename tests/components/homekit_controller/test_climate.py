"""Basic checks for HomeKitclimate."""
from homeassistant.components.climate.const import (
    DOMAIN, SERVICE_SET_OPERATION_MODE, SERVICE_SET_TEMPERATURE)
from tests.components.homekit_controller.common import (
    FakeService, setup_test_component)


HEATING_COOLING_TARGET = ('thermostat', 'heating-cooling.target')
HEATING_COOLING_CURRENT = ('thermostat', 'heating-cooling.current')
TEMPERATURE_TARGET = ('thermostat', 'temperature.target')
TEMPERATURE_CURRENT = ('thermostat', 'temperature.current')


async def test_climate_respect_supported_op_modes_1(hass, utcnow):
    """Test that climate respects minValue/maxValue hints."""
    service = FakeService('public.hap.service.thermostat')
    char = service.add_characteristic('heating-cooling.target')
    char.value = 0
    char.minValue = 0
    char.maxValue = 1

    helper = await setup_test_component(hass, [service])

    state = await helper.poll_and_get_state()
    assert state.attributes['operation_list'] == ['off', 'heat']


async def test_climate_respect_supported_op_modes_2(hass, utcnow):
    """Test that climate respects validValue hints."""
    service = FakeService('public.hap.service.thermostat')
    char = service.add_characteristic('heating-cooling.target')
    char.value = 0
    char.validValues = [0, 1, 2]

    helper = await setup_test_component(hass, [service])

    state = await helper.poll_and_get_state()
    assert state.attributes['operation_list'] == ['off', 'heat', 'cool']


async def test_climate_change_thermostat_state(hass, utcnow):
    """Test that we can turn a HomeKit thermostat on and off again."""
    from homekit.model.services import ThermostatService

    helper = await setup_test_component(hass, [ThermostatService()])

    await hass.services.async_call(DOMAIN, SERVICE_SET_OPERATION_MODE, {
        'entity_id': 'climate.testdevice',
        'operation_mode': 'heat',
    }, blocking=True)

    assert helper.characteristics[HEATING_COOLING_TARGET].value == 1

    await hass.services.async_call(DOMAIN, SERVICE_SET_OPERATION_MODE, {
        'entity_id': 'climate.testdevice',
        'operation_mode': 'cool',
    }, blocking=True)
    assert helper.characteristics[HEATING_COOLING_TARGET].value == 2


async def test_climate_change_thermostat_temperature(hass, utcnow):
    """Test that we can turn a HomeKit thermostat on and off again."""
    from homekit.model.services import ThermostatService

    helper = await setup_test_component(hass, [ThermostatService()])

    await hass.services.async_call(DOMAIN, SERVICE_SET_TEMPERATURE, {
        'entity_id': 'climate.testdevice',
        'temperature': 21,
    }, blocking=True)
    assert helper.characteristics[TEMPERATURE_TARGET].value == 21

    await hass.services.async_call(DOMAIN, SERVICE_SET_TEMPERATURE, {
        'entity_id': 'climate.testdevice',
        'temperature': 25,
    }, blocking=True)
    assert helper.characteristics[TEMPERATURE_TARGET].value == 25


async def test_climate_read_thermostat_state(hass, utcnow):
    """Test that we can read the state of a HomeKit thermostat accessory."""
    from homekit.model.services import ThermostatService

    helper = await setup_test_component(hass, [ThermostatService()])

    # Simulate that heating is on
    helper.characteristics[TEMPERATURE_CURRENT].value = 19
    helper.characteristics[TEMPERATURE_TARGET].value = 21
    helper.characteristics[HEATING_COOLING_CURRENT].value = 1
    helper.characteristics[HEATING_COOLING_TARGET].value = 1

    state = await helper.poll_and_get_state()
    assert state.state == 'heat'
    assert state.attributes['current_temperature'] == 19

    # Simulate that cooling is on
    helper.characteristics[TEMPERATURE_CURRENT].value = 21
    helper.characteristics[TEMPERATURE_TARGET].value = 19
    helper.characteristics[HEATING_COOLING_CURRENT].value = 2
    helper.characteristics[HEATING_COOLING_TARGET].value = 2

    state = await helper.poll_and_get_state()
    assert state.state == 'cool'
    assert state.attributes['current_temperature'] == 21
