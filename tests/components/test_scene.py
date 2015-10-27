"""
tests.components.test_scene
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests scene component.
"""
import unittest

from homeassistant import loader
from homeassistant.components import light, scene

from tests.common import get_test_home_assistant


class TestScene(unittest.TestCase):
    """ Test scene component. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_config_not_list(self):
        self.assertFalse(scene.setup(self.hass, {
            'scene': {'some': 'dict'}
        }))

    def test_config_no_dict_in_list(self):
        self.assertFalse(scene.setup(self.hass, {
            'scene': [[]]
        }))

    def test_activate_scene(self):
        test_light = loader.get_component('light.test')
        test_light.init()

        self.assertTrue(light.setup(self.hass, {
            light.DOMAIN: {'platform': 'test'}
        }))

        light_1, light_2 = test_light.DEVICES[0:2]

        light.turn_off(self.hass, [light_1.entity_id, light_2.entity_id])

        self.hass.pool.block_till_done()

        self.assertTrue(scene.setup(self.hass, {
            'scene': [{
                'name': 'test',
                'entities': {
                    light_1.entity_id: 'on',
                    light_2.entity_id: {
                        'state': 'on',
                        'brightness': 100,
                    }
                }
            }]
        }))

        scene.activate(self.hass, 'scene.test')
        self.hass.pool.block_till_done()

        self.assertTrue(light_1.is_on)
        self.assertTrue(light_2.is_on)
        self.assertEqual(100,
                         light_2.last_call('turn_on')[1].get('brightness'))
