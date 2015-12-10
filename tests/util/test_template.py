"""
tests.test_util
~~~~~~~~~~~~~~~~~

Tests Home Assistant util methods.
"""
# pylint: disable=too-many-public-methods
import unittest
import homeassistant.core as ha

from homeassistant.util import template


class TestUtilTemplate(unittest.TestCase):

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = ha.HomeAssistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_referring_states_by_entity_id(self):
        self.hass.states.set('test.object', 'happy')
        self.assertEqual(
            'happy',
            template.render(self.hass, '{{ states.test.object.state }}'))

    def test_iterating_all_states(self):
        self.hass.states.set('test.object', 'happy')
        self.hass.states.set('sensor.temperature', 10)

        self.assertEqual(
            '10happy',
            template.render(
                self.hass,
                '{% for state in states %}{{ state.state }}{% endfor %}'))

    def test_iterating_domain_states(self):
        self.hass.states.set('test.object', 'happy')
        self.hass.states.set('sensor.back_door', 'open')
        self.hass.states.set('sensor.temperature', 10)

        self.assertEqual(
            'open10',
            template.render(
                self.hass,
                '{% for state in states.sensor %}{{ state.state }}{% endfor %}'))

    def test_rounding_value(self):
        self.hass.states.set('sensor.temperature', 12.34)

        self.assertEqual(
            '12.3',
            template.render(
                self.hass,
                '{{ states.sensor.temperature.state | round(1) }}'))
