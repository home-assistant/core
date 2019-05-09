"""Basic checks for HomeKitSwitch."""
from tests.components.homekit_controller.common import (
    FakeService, setup_test_component)


LIGHT_ON = ('lightbulb', 'on')
LIGHT_BRIGHTNESS = ('lightbulb', 'brightness')
LIGHT_HUE = ('lightbulb', 'hue')
LIGHT_SATURATION = ('lightbulb', 'saturation')
LIGHT_COLOR_TEMP = ('lightbulb', 'color-temperature')


def create_lightbulb_service():
    """Define lightbulb characteristics."""
    service = FakeService('public.hap.service.lightbulb')

    on_char = service.add_characteristic('on')
    on_char.value = 0

    brightness = service.add_characteristic('brightness')
    brightness.value = 0

    return service


def create_lightbulb_service_with_hs():
    """Define a lightbulb service with hue + saturation."""
    service = create_lightbulb_service()

    hue = service.add_characteristic('hue')
    hue.value = 0

    saturation = service.add_characteristic('saturation')
    saturation.value = 0

    return service


def create_lightbulb_service_with_color_temp():
    """Define a lightbulb service with color temp."""
    service = create_lightbulb_service()

    color_temp = service.add_characteristic('color-temperature')
    color_temp.value = 0

    return service


async def test_switch_change_light_state(hass, utcnow):
    """Test that we can turn a HomeKit light on and off again."""
    bulb = create_lightbulb_service_with_hs()
    helper = await setup_test_component(hass, [bulb])

    await hass.services.async_call('light', 'turn_on', {
        'entity_id': 'light.testdevice',
        'brightness': 255,
        'hs_color': [4, 5],
    }, blocking=True)

    assert helper.characteristics[LIGHT_ON].value == 1
    assert helper.characteristics[LIGHT_BRIGHTNESS].value == 100
    assert helper.characteristics[LIGHT_HUE].value == 4
    assert helper.characteristics[LIGHT_SATURATION].value == 5

    await hass.services.async_call('light', 'turn_off', {
        'entity_id': 'light.testdevice',
    }, blocking=True)
    assert helper.characteristics[LIGHT_ON].value == 0


async def test_switch_change_light_state_color_temp(hass, utcnow):
    """Test that we can turn change color_temp."""
    bulb = create_lightbulb_service_with_color_temp()
    helper = await setup_test_component(hass, [bulb])

    await hass.services.async_call('light', 'turn_on', {
        'entity_id': 'light.testdevice',
        'brightness': 255,
        'color_temp': 400,
    }, blocking=True)
    assert helper.characteristics[LIGHT_ON].value == 1
    assert helper.characteristics[LIGHT_BRIGHTNESS].value == 100
    assert helper.characteristics[LIGHT_COLOR_TEMP].value == 400


async def test_switch_read_light_state(hass, utcnow):
    """Test that we can read the state of a HomeKit light accessory."""
    bulb = create_lightbulb_service_with_hs()
    helper = await setup_test_component(hass, [bulb])

    # Initial state is that the light is off
    state = await helper.poll_and_get_state()
    assert state.state == 'off'

    # Simulate that someone switched on the device in the real world not via HA
    helper.characteristics[LIGHT_ON].set_value(True)
    helper.characteristics[LIGHT_BRIGHTNESS].value = 100
    helper.characteristics[LIGHT_HUE].value = 4
    helper.characteristics[LIGHT_SATURATION].value = 5
    state = await helper.poll_and_get_state()
    assert state.state == 'on'
    assert state.attributes['brightness'] == 255
    assert state.attributes['hs_color'] == (4, 5)

    # Simulate that device switched off in the real world not via HA
    helper.characteristics[LIGHT_ON].set_value(False)
    state = await helper.poll_and_get_state()
    assert state.state == 'off'


async def test_switch_read_light_state_color_temp(hass, utcnow):
    """Test that we can read the color_temp of a  light accessory."""
    bulb = create_lightbulb_service_with_color_temp()
    helper = await setup_test_component(hass, [bulb])

    # Initial state is that the light is off
    state = await helper.poll_and_get_state()
    assert state.state == 'off'

    # Simulate that someone switched on the device in the real world not via HA
    helper.characteristics[LIGHT_ON].set_value(True)
    helper.characteristics[LIGHT_BRIGHTNESS].value = 100
    helper.characteristics[LIGHT_COLOR_TEMP].value = 400

    state = await helper.poll_and_get_state()
    assert state.state == 'on'
    assert state.attributes['brightness'] == 255
    assert state.attributes['color_temp'] == 400


async def test_light_becomes_unavailable_but_recovers(hass, utcnow):
    """Test transition to and from unavailable state."""
    bulb = create_lightbulb_service_with_color_temp()
    helper = await setup_test_component(hass, [bulb])

    # Initial state is that the light is off
    state = await helper.poll_and_get_state()
    assert state.state == 'off'

    # Test device goes offline
    helper.pairing.available = False
    state = await helper.poll_and_get_state()
    assert state.state == 'unavailable'

    # Simulate that someone switched on the device in the real world not via HA
    helper.characteristics[LIGHT_ON].set_value(True)
    helper.characteristics[LIGHT_BRIGHTNESS].value = 100
    helper.characteristics[LIGHT_COLOR_TEMP].value = 400
    helper.pairing.available = True

    state = await helper.poll_and_get_state()
    assert state.state == 'on'
    assert state.attributes['brightness'] == 255
    assert state.attributes['color_temp'] == 400
