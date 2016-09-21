"""The tests for the Light component."""
# pylint: disable=too-many-public-methods,protected-access
import unittest
import os

from homeassistant.bootstrap import setup_component
import homeassistant.loader as loader
from homeassistant.const import (
    ATTR_ENTITY_ID, STATE_ON, STATE_OFF, CONF_PLATFORM,
    SERVICE_TURN_ON, SERVICE_TURN_OFF, SERVICE_TOGGLE)
import homeassistant.components.light as light

from tests.common import mock_service, get_test_home_assistant


class TestLight(unittest.TestCase):
    """Test the light module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

        user_light_file = self.hass.config.path(light.LIGHT_PROFILES_FILE)

        if os.path.isfile(user_light_file):
            os.remove(user_light_file)

    def test_methods(self):
        """Test if methods call the services as expected."""
        # Test is_on
        self.hass.states.set('light.test', STATE_ON)
        self.assertTrue(light.is_on(self.hass, 'light.test'))

        self.hass.states.set('light.test', STATE_OFF)
        self.assertFalse(light.is_on(self.hass, 'light.test'))

        self.hass.states.set(light.ENTITY_ID_ALL_LIGHTS, STATE_ON)
        self.assertTrue(light.is_on(self.hass))

        self.hass.states.set(light.ENTITY_ID_ALL_LIGHTS, STATE_OFF)
        self.assertFalse(light.is_on(self.hass))

        # Test turn_on
        turn_on_calls = mock_service(
            self.hass, light.DOMAIN, SERVICE_TURN_ON)

        light.turn_on(
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

        self.assertEqual(1, len(turn_on_calls))
        call = turn_on_calls[-1]

        self.assertEqual(light.DOMAIN, call.domain)
        self.assertEqual(SERVICE_TURN_ON, call.service)
        self.assertEqual('entity_id_val', call.data.get(ATTR_ENTITY_ID))
        self.assertEqual(
            'transition_val', call.data.get(light.ATTR_TRANSITION))
        self.assertEqual(
            'brightness_val', call.data.get(light.ATTR_BRIGHTNESS))
        self.assertEqual('rgb_color_val', call.data.get(light.ATTR_RGB_COLOR))
        self.assertEqual('xy_color_val', call.data.get(light.ATTR_XY_COLOR))
        self.assertEqual('profile_val', call.data.get(light.ATTR_PROFILE))
        self.assertEqual(
            'color_name_val', call.data.get(light.ATTR_COLOR_NAME))
        self.assertEqual('white_val', call.data.get(light.ATTR_WHITE_VALUE))

        # Test turn_off
        turn_off_calls = mock_service(
            self.hass, light.DOMAIN, SERVICE_TURN_OFF)

        light.turn_off(
            self.hass, entity_id='entity_id_val', transition='transition_val')

        self.hass.block_till_done()

        self.assertEqual(1, len(turn_off_calls))
        call = turn_off_calls[-1]

        self.assertEqual(light.DOMAIN, call.domain)
        self.assertEqual(SERVICE_TURN_OFF, call.service)
        self.assertEqual('entity_id_val', call.data[ATTR_ENTITY_ID])
        self.assertEqual('transition_val', call.data[light.ATTR_TRANSITION])

        # Test toggle
        toggle_calls = mock_service(
            self.hass, light.DOMAIN, SERVICE_TOGGLE)

        light.toggle(
            self.hass, entity_id='entity_id_val', transition='transition_val')

        self.hass.block_till_done()

        self.assertEqual(1, len(toggle_calls))
        call = toggle_calls[-1]

        self.assertEqual(light.DOMAIN, call.domain)
        self.assertEqual(SERVICE_TOGGLE, call.service)
        self.assertEqual('entity_id_val', call.data[ATTR_ENTITY_ID])
        self.assertEqual('transition_val', call.data[light.ATTR_TRANSITION])

    def test_services(self):
        """Test the provided services."""
        platform = loader.get_component('light.test')

        platform.init()
        self.assertTrue(
            setup_component(self.hass, light.DOMAIN,
                            {light.DOMAIN: {CONF_PLATFORM: 'test'}}))

        dev1, dev2, dev3 = platform.DEVICES

        # Test init
        self.assertTrue(light.is_on(self.hass, dev1.entity_id))
        self.assertFalse(light.is_on(self.hass, dev2.entity_id))
        self.assertFalse(light.is_on(self.hass, dev3.entity_id))

        # Test basic turn_on, turn_off, toggle services
        light.turn_off(self.hass, entity_id=dev1.entity_id)
        light.turn_on(self.hass, entity_id=dev2.entity_id)

        self.hass.block_till_done()

        self.assertFalse(light.is_on(self.hass, dev1.entity_id))
        self.assertTrue(light.is_on(self.hass, dev2.entity_id))

        # turn on all lights
        light.turn_on(self.hass)

        self.hass.block_till_done()

        self.assertTrue(light.is_on(self.hass, dev1.entity_id))
        self.assertTrue(light.is_on(self.hass, dev2.entity_id))
        self.assertTrue(light.is_on(self.hass, dev3.entity_id))

        # turn off all lights
        light.turn_off(self.hass)

        self.hass.block_till_done()

        self.assertFalse(light.is_on(self.hass, dev1.entity_id))
        self.assertFalse(light.is_on(self.hass, dev2.entity_id))
        self.assertFalse(light.is_on(self.hass, dev3.entity_id))

        # toggle all lights
        light.toggle(self.hass)

        self.hass.block_till_done()

        self.assertTrue(light.is_on(self.hass, dev1.entity_id))
        self.assertTrue(light.is_on(self.hass, dev2.entity_id))
        self.assertTrue(light.is_on(self.hass, dev3.entity_id))

        # toggle all lights
        light.toggle(self.hass)

        self.hass.block_till_done()

        self.assertFalse(light.is_on(self.hass, dev1.entity_id))
        self.assertFalse(light.is_on(self.hass, dev2.entity_id))
        self.assertFalse(light.is_on(self.hass, dev3.entity_id))

        # Ensure all attributes process correctly
        light.turn_on(self.hass, dev1.entity_id,
                      transition=10, brightness=20, color_name='blue')
        light.turn_on(
            self.hass, dev2.entity_id, rgb_color=(255, 255, 255),
            white_value=255)
        light.turn_on(self.hass, dev3.entity_id, xy_color=(.4, .6))

        self.hass.block_till_done()

        _, data = dev1.last_call('turn_on')
        self.assertEqual(
            {light.ATTR_TRANSITION: 10,
             light.ATTR_BRIGHTNESS: 20,
             light.ATTR_RGB_COLOR: (0, 0, 255)},
            data)

        _, data = dev2.last_call('turn_on')
        self.assertEqual(
            {light.ATTR_RGB_COLOR: (255, 255, 255),
             light.ATTR_WHITE_VALUE: 255},
            data)

        _, data = dev3.last_call('turn_on')
        self.assertEqual({light.ATTR_XY_COLOR: (.4, .6)}, data)

        # One of the light profiles
        prof_name, prof_x, prof_y, prof_bri = 'relax', 0.5119, 0.4147, 144

        # Test light profiles
        light.turn_on(self.hass, dev1.entity_id, profile=prof_name)
        # Specify a profile and attributes to overwrite it
        light.turn_on(
            self.hass, dev2.entity_id,
            profile=prof_name, brightness=100, xy_color=(.4, .6))

        self.hass.block_till_done()

        _, data = dev1.last_call('turn_on')
        self.assertEqual(
            {light.ATTR_BRIGHTNESS: prof_bri,
             light.ATTR_XY_COLOR: (prof_x, prof_y)},
            data)

        _, data = dev2.last_call('turn_on')
        self.assertEqual(
            {light.ATTR_BRIGHTNESS: 100,
             light.ATTR_XY_COLOR: (.4, .6)},
            data)

        # Test shitty data
        light.turn_on(self.hass)
        light.turn_on(self.hass, dev1.entity_id, profile="nonexisting")
        light.turn_on(self.hass, dev2.entity_id, xy_color=["bla-di-bla", 5])
        light.turn_on(self.hass, dev3.entity_id, rgb_color=[255, None, 2])

        self.hass.block_till_done()

        _, data = dev1.last_call('turn_on')
        self.assertEqual({}, data)

        _, data = dev2.last_call('turn_on')
        self.assertEqual({}, data)

        _, data = dev3.last_call('turn_on')
        self.assertEqual({}, data)

        # faulty attributes will not trigger a service call
        light.turn_on(
            self.hass, dev1.entity_id,
            profile=prof_name, brightness='bright', rgb_color='yellowish')
        light.turn_on(
            self.hass, dev2.entity_id,
            white_value='high')

        self.hass.block_till_done()

        _, data = dev1.last_call('turn_on')
        self.assertEqual({}, data)

        _, data = dev2.last_call('turn_on')
        self.assertEqual({}, data)

    def test_broken_light_profiles(self):
        """Test light profiles."""
        platform = loader.get_component('light.test')
        platform.init()

        user_light_file = self.hass.config.path(light.LIGHT_PROFILES_FILE)

        # Setup a wrong light file
        with open(user_light_file, 'w') as user_file:
            user_file.write('id,x,y,brightness\n')
            user_file.write('I,WILL,NOT,WORK\n')

        self.assertFalse(setup_component(
            self.hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: 'test'}}
        ))

    def test_light_profiles(self):
        """Test light profiles."""
        platform = loader.get_component('light.test')
        platform.init()

        user_light_file = self.hass.config.path(light.LIGHT_PROFILES_FILE)

        with open(user_light_file, 'w') as user_file:
            user_file.write('id,x,y,brightness\n')
            user_file.write('test,.4,.6,100\n')

        self.assertTrue(setup_component(
            self.hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: 'test'}}
        ))

        dev1, _, _ = platform.DEVICES

        light.turn_on(self.hass, dev1.entity_id, profile='test')

        self.hass.block_till_done()

        _, data = dev1.last_call('turn_on')

        self.assertEqual(
            {light.ATTR_XY_COLOR: (.4, .6), light.ATTR_BRIGHTNESS: 100},
            data)
