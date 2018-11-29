"""The tests for the Light component."""
# pylint: disable=protected-access
import unittest
import unittest.mock as mock
import os
from io import StringIO

from homeassistant import core, loader
from homeassistant.setup import setup_component, async_setup_component
from homeassistant.const import (
    ATTR_ENTITY_ID, STATE_ON, STATE_OFF, CONF_PLATFORM,
    SERVICE_TURN_ON, SERVICE_TURN_OFF, SERVICE_TOGGLE, ATTR_SUPPORTED_FEATURES)
from homeassistant.components import light
from homeassistant.helpers.intent import IntentHandleError

from tests.common import (
    async_mock_service, mock_service, get_test_home_assistant, mock_storage)
from tests.components.light import common


class TestLight(unittest.TestCase):
    """Test the light module."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

        user_light_file = self.hass.config.path(light.LIGHT_PROFILES_FILE)

        if os.path.isfile(user_light_file):
            os.remove(user_light_file)

    def test_methods(self):
        """Test if methods call the services as expected."""
        # Test is_on
        self.hass.states.set('light.test', STATE_ON)
        assert light.is_on(self.hass, 'light.test')

        self.hass.states.set('light.test', STATE_OFF)
        assert not light.is_on(self.hass, 'light.test')

        self.hass.states.set(light.ENTITY_ID_ALL_LIGHTS, STATE_ON)
        assert light.is_on(self.hass)

        self.hass.states.set(light.ENTITY_ID_ALL_LIGHTS, STATE_OFF)
        assert not light.is_on(self.hass)

        # Test turn_on
        turn_on_calls = mock_service(
            self.hass, light.DOMAIN, SERVICE_TURN_ON)

        common.turn_on(
            self.hass,
            entity_id='entity_id_val',
            transition='transition_val',
            brightness='brightness_val',
            rgb_color='rgb_color_val',
            xy_color='xy_color_val',
            profile='profile_val',
            color_name='color_name_val',
            white_value='white_val')

        self.hass.block_till_done()

        assert 1 == len(turn_on_calls)
        call = turn_on_calls[-1]

        assert light.DOMAIN == call.domain
        assert SERVICE_TURN_ON == call.service
        assert 'entity_id_val' == call.data.get(ATTR_ENTITY_ID)
        assert 'transition_val' == call.data.get(light.ATTR_TRANSITION)
        assert 'brightness_val' == call.data.get(light.ATTR_BRIGHTNESS)
        assert 'rgb_color_val' == call.data.get(light.ATTR_RGB_COLOR)
        assert 'xy_color_val' == call.data.get(light.ATTR_XY_COLOR)
        assert 'profile_val' == call.data.get(light.ATTR_PROFILE)
        assert 'color_name_val' == call.data.get(light.ATTR_COLOR_NAME)
        assert 'white_val' == call.data.get(light.ATTR_WHITE_VALUE)

        # Test turn_off
        turn_off_calls = mock_service(
            self.hass, light.DOMAIN, SERVICE_TURN_OFF)

        common.turn_off(
            self.hass, entity_id='entity_id_val', transition='transition_val')

        self.hass.block_till_done()

        assert 1 == len(turn_off_calls)
        call = turn_off_calls[-1]

        assert light.DOMAIN == call.domain
        assert SERVICE_TURN_OFF == call.service
        assert 'entity_id_val' == call.data[ATTR_ENTITY_ID]
        assert 'transition_val' == call.data[light.ATTR_TRANSITION]

        # Test toggle
        toggle_calls = mock_service(
            self.hass, light.DOMAIN, SERVICE_TOGGLE)

        common.toggle(
            self.hass, entity_id='entity_id_val', transition='transition_val')

        self.hass.block_till_done()

        assert 1 == len(toggle_calls)
        call = toggle_calls[-1]

        assert light.DOMAIN == call.domain
        assert SERVICE_TOGGLE == call.service
        assert 'entity_id_val' == call.data[ATTR_ENTITY_ID]
        assert 'transition_val' == call.data[light.ATTR_TRANSITION]

    def test_services(self):
        """Test the provided services."""
        platform = loader.get_component(self.hass, 'light.test')

        platform.init()
        assert setup_component(self.hass, light.DOMAIN,
                               {light.DOMAIN: {CONF_PLATFORM: 'test'}})

        dev1, dev2, dev3 = platform.DEVICES

        # Test init
        assert light.is_on(self.hass, dev1.entity_id)
        assert not light.is_on(self.hass, dev2.entity_id)
        assert not light.is_on(self.hass, dev3.entity_id)

        # Test basic turn_on, turn_off, toggle services
        common.turn_off(self.hass, entity_id=dev1.entity_id)
        common.turn_on(self.hass, entity_id=dev2.entity_id)

        self.hass.block_till_done()

        assert not light.is_on(self.hass, dev1.entity_id)
        assert light.is_on(self.hass, dev2.entity_id)

        # turn on all lights
        common.turn_on(self.hass)

        self.hass.block_till_done()

        assert light.is_on(self.hass, dev1.entity_id)
        assert light.is_on(self.hass, dev2.entity_id)
        assert light.is_on(self.hass, dev3.entity_id)

        # turn off all lights
        common.turn_off(self.hass)

        self.hass.block_till_done()

        assert not light.is_on(self.hass, dev1.entity_id)
        assert not light.is_on(self.hass, dev2.entity_id)
        assert not light.is_on(self.hass, dev3.entity_id)

        # toggle all lights
        common.toggle(self.hass)

        self.hass.block_till_done()

        assert light.is_on(self.hass, dev1.entity_id)
        assert light.is_on(self.hass, dev2.entity_id)
        assert light.is_on(self.hass, dev3.entity_id)

        # toggle all lights
        common.toggle(self.hass)

        self.hass.block_till_done()

        assert not light.is_on(self.hass, dev1.entity_id)
        assert not light.is_on(self.hass, dev2.entity_id)
        assert not light.is_on(self.hass, dev3.entity_id)

        # Ensure all attributes process correctly
        common.turn_on(self.hass, dev1.entity_id,
                       transition=10, brightness=20, color_name='blue')
        common.turn_on(
            self.hass, dev2.entity_id, rgb_color=(255, 255, 255),
            white_value=255)
        common.turn_on(self.hass, dev3.entity_id, xy_color=(.4, .6))

        self.hass.block_till_done()

        _, data = dev1.last_call('turn_on')
        assert {
            light.ATTR_TRANSITION: 10,
            light.ATTR_BRIGHTNESS: 20,
            light.ATTR_HS_COLOR: (240, 100),
        } == data

        _, data = dev2.last_call('turn_on')
        assert {
            light.ATTR_HS_COLOR: (0, 0),
            light.ATTR_WHITE_VALUE: 255,
        } == data

        _, data = dev3.last_call('turn_on')
        assert {
            light.ATTR_HS_COLOR: (71.059, 100),
        } == data

        # One of the light profiles
        prof_name, prof_h, prof_s, prof_bri = 'relax', 35.932, 69.412, 144

        # Test light profiles
        common.turn_on(self.hass, dev1.entity_id, profile=prof_name)
        # Specify a profile and a brightness attribute to overwrite it
        common.turn_on(
            self.hass, dev2.entity_id,
            profile=prof_name, brightness=100)

        self.hass.block_till_done()

        _, data = dev1.last_call('turn_on')
        assert {
            light.ATTR_BRIGHTNESS: prof_bri,
            light.ATTR_HS_COLOR: (prof_h, prof_s),
        } == data

        _, data = dev2.last_call('turn_on')
        assert {
            light.ATTR_BRIGHTNESS: 100,
            light.ATTR_HS_COLOR: (prof_h, prof_s),
        } == data

        # Test bad data
        common.turn_on(self.hass)
        common.turn_on(self.hass, dev1.entity_id, profile="nonexisting")
        common.turn_on(self.hass, dev2.entity_id, xy_color=["bla-di-bla", 5])
        common.turn_on(self.hass, dev3.entity_id, rgb_color=[255, None, 2])

        self.hass.block_till_done()

        _, data = dev1.last_call('turn_on')
        assert {} == data

        _, data = dev2.last_call('turn_on')
        assert {} == data

        _, data = dev3.last_call('turn_on')
        assert {} == data

        # faulty attributes will not trigger a service call
        common.turn_on(
            self.hass, dev1.entity_id,
            profile=prof_name, brightness='bright')
        common.turn_on(
            self.hass, dev1.entity_id,
            rgb_color='yellowish')
        common.turn_on(
            self.hass, dev2.entity_id,
            white_value='high')

        self.hass.block_till_done()

        _, data = dev1.last_call('turn_on')
        assert {} == data

        _, data = dev2.last_call('turn_on')
        assert {} == data

    def test_broken_light_profiles(self):
        """Test light profiles."""
        platform = loader.get_component(self.hass, 'light.test')
        platform.init()

        user_light_file = self.hass.config.path(light.LIGHT_PROFILES_FILE)

        # Setup a wrong light file
        with open(user_light_file, 'w') as user_file:
            user_file.write('id,x,y,brightness\n')
            user_file.write('I,WILL,NOT,WORK\n')

        assert not setup_component(
            self.hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: 'test'}})

    def test_light_profiles(self):
        """Test light profiles."""
        platform = loader.get_component(self.hass, 'light.test')
        platform.init()

        user_light_file = self.hass.config.path(light.LIGHT_PROFILES_FILE)

        with open(user_light_file, 'w') as user_file:
            user_file.write('id,x,y,brightness\n')
            user_file.write('test,.4,.6,100\n')

        assert setup_component(
            self.hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: 'test'}}
        )

        dev1, _, _ = platform.DEVICES

        common.turn_on(self.hass, dev1.entity_id, profile='test')

        self.hass.block_till_done()

        _, data = dev1.last_call('turn_on')

        assert {
            light.ATTR_HS_COLOR: (71.059, 100),
            light.ATTR_BRIGHTNESS: 100
        } == data

    def test_default_profiles_group(self):
        """Test default turn-on light profile for all lights."""
        platform = loader.get_component(self.hass, 'light.test')
        platform.init()

        user_light_file = self.hass.config.path(light.LIGHT_PROFILES_FILE)
        real_isfile = os.path.isfile
        real_open = open

        def _mock_isfile(path):
            if path == user_light_file:
                return True
            return real_isfile(path)

        def _mock_open(path):
            if path == user_light_file:
                return StringIO(profile_data)
            return real_open(path)

        profile_data = "id,x,y,brightness\n" +\
                       "group.all_lights.default,.4,.6,99\n"
        with mock.patch('os.path.isfile', side_effect=_mock_isfile):
            with mock.patch('builtins.open', side_effect=_mock_open):
                with mock_storage():
                    assert setup_component(
                        self.hass, light.DOMAIN,
                        {light.DOMAIN: {CONF_PLATFORM: 'test'}}
                    )

        dev, _, _ = platform.DEVICES
        common.turn_on(self.hass, dev.entity_id)
        self.hass.block_till_done()
        _, data = dev.last_call('turn_on')
        assert {
            light.ATTR_HS_COLOR: (71.059, 100),
            light.ATTR_BRIGHTNESS: 99
        } == data

    def test_default_profiles_light(self):
        """Test default turn-on light profile for a specific light."""
        platform = loader.get_component(self.hass, 'light.test')
        platform.init()

        user_light_file = self.hass.config.path(light.LIGHT_PROFILES_FILE)
        real_isfile = os.path.isfile
        real_open = open

        def _mock_isfile(path):
            if path == user_light_file:
                return True
            return real_isfile(path)

        def _mock_open(path):
            if path == user_light_file:
                return StringIO(profile_data)
            return real_open(path)

        profile_data = "id,x,y,brightness\n" +\
                       "group.all_lights.default,.3,.5,200\n" +\
                       "light.ceiling_2.default,.6,.6,100\n"
        with mock.patch('os.path.isfile', side_effect=_mock_isfile):
            with mock.patch('builtins.open', side_effect=_mock_open):
                with mock_storage():
                    assert setup_component(
                        self.hass, light.DOMAIN,
                        {light.DOMAIN: {CONF_PLATFORM: 'test'}}
                    )

        dev = next(filter(lambda x: x.entity_id == 'light.ceiling_2',
                          platform.DEVICES))
        common.turn_on(self.hass, dev.entity_id)
        self.hass.block_till_done()
        _, data = dev.last_call('turn_on')
        assert {
            light.ATTR_HS_COLOR: (50.353, 100),
            light.ATTR_BRIGHTNESS: 100
        } == data


async def test_intent_set_color(hass):
    """Test the set color intent."""
    hass.states.async_set('light.hello_2', 'off', {
        ATTR_SUPPORTED_FEATURES: light.SUPPORT_COLOR
    })
    hass.states.async_set('switch.hello', 'off')
    calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)
    hass.helpers.intent.async_register(light.SetIntentHandler())

    result = await hass.helpers.intent.async_handle(
        'test', light.INTENT_SET, {
            'name': {
                'value': 'Hello',
            },
            'color': {
                'value': 'blue'
            }
        })
    await hass.async_block_till_done()

    assert result.speech['plain']['speech'] == \
        'Changed hello 2 to the color blue'

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == light.DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data.get(ATTR_ENTITY_ID) == 'light.hello_2'
    assert call.data.get(light.ATTR_RGB_COLOR) == (0, 0, 255)


async def test_intent_set_color_tests_feature(hass):
    """Test the set color intent."""
    hass.states.async_set('light.hello', 'off')
    calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)
    hass.helpers.intent.async_register(light.SetIntentHandler())

    try:
        await hass.helpers.intent.async_handle(
            'test', light.INTENT_SET, {
                'name': {
                    'value': 'Hello',
                },
                'color': {
                    'value': 'blue'
                }
            })
        assert False, 'handling intent should have raised'
    except IntentHandleError as err:
        assert str(err) == 'Entity hello does not support changing colors'

    assert len(calls) == 0


async def test_intent_set_color_and_brightness(hass):
    """Test the set color intent."""
    hass.states.async_set('light.hello_2', 'off', {
        ATTR_SUPPORTED_FEATURES: (
            light.SUPPORT_COLOR | light.SUPPORT_BRIGHTNESS)
    })
    hass.states.async_set('switch.hello', 'off')
    calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)
    hass.helpers.intent.async_register(light.SetIntentHandler())

    result = await hass.helpers.intent.async_handle(
        'test', light.INTENT_SET, {
            'name': {
                'value': 'Hello',
            },
            'color': {
                'value': 'blue'
            },
            'brightness': {
                'value': '20'
            }
        })
    await hass.async_block_till_done()

    assert result.speech['plain']['speech'] == \
        'Changed hello 2 to the color blue and 20% brightness'

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == light.DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data.get(ATTR_ENTITY_ID) == 'light.hello_2'
    assert call.data.get(light.ATTR_RGB_COLOR) == (0, 0, 255)
    assert call.data.get(light.ATTR_BRIGHTNESS_PCT) == 20


async def test_light_context(hass, hass_admin_user):
    """Test that light context works."""
    assert await async_setup_component(hass, 'light', {
        'light': {
            'platform': 'test'
        }
    })

    state = hass.states.get('light.ceiling')
    assert state is not None

    await hass.services.async_call('light', 'toggle', {
        'entity_id': state.entity_id,
    }, True, core.Context(user_id=hass_admin_user.id))

    state2 = hass.states.get('light.ceiling')
    assert state2 is not None
    assert state.state != state2.state
    assert state2.context.user_id == hass_admin_user.id
