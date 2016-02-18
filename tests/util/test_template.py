"""
tests.util.test_template
~~~~~~~~~~~~~~~~~~~~~~~~

Tests Home Assistant template util methods.
"""
# pylint: disable=too-many-public-methods
import unittest
from homeassistant.exceptions import TemplateError
from homeassistant.util import template

from tests.common import get_test_home_assistant


class TestUtilTemplate(unittest.TestCase):

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = get_test_home_assistant()

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
                """
{% for state in states.sensor %}{{ state.state }}{% endfor %}
                """))

    def test_rounding_value(self):
        self.hass.states.set('sensor.temperature', 12.78)

        self.assertEqual(
            '12.8',
            template.render(
                self.hass,
                '{{ states.sensor.temperature.state | round(1) }}'))

    def test_rounding_value2(self):
        self.hass.states.set('sensor.temperature', 12.78)

        self.assertEqual(
            '128',
            template.render(
                self.hass,
                '{{ states.sensor.temperature.state | multiply(10) | round }}'
            ))

    def test_passing_vars_as_keywords(self):
        self.assertEqual(
            '127', template.render(self.hass, '{{ hello }}', hello=127))

    def test_passing_vars_as_vars(self):
        self.assertEqual(
            '127', template.render(self.hass, '{{ hello }}', {'hello': 127}))

    def test_render_with_possible_json_value_with_valid_json(self):
        self.assertEqual(
            'world',
            template.render_with_possible_json_value(
                self.hass, '{{ value_json.hello }}', '{"hello": "world"}'))

    def test_render_with_possible_json_value_with_invalid_json(self):
        self.assertEqual(
            '',
            template.render_with_possible_json_value(
                self.hass, '{{ value_json }}', '{ I AM NOT JSON }'))

    def test_render_with_possible_json_value_with_template_error(self):
        self.assertEqual(
            'hello',
            template.render_with_possible_json_value(
                self.hass, '{{ value_json', 'hello'))

    def test_render_with_possible_json_value_with_template_error_value(self):
        self.assertEqual(
            '-',
            template.render_with_possible_json_value(
                self.hass, '{{ value_json', 'hello', '-'))

    def test_raise_exception_on_error(self):
        with self.assertRaises(TemplateError):
            template.render(self.hass, '{{ invalid_syntax')

    def test_if_state_exists(self):
        self.hass.states.set('test.object', 'available')
        self.assertEqual(
            'exists',
            template.render(
                self.hass,
                """
{% if states.test.object %}exists{% else %}not exists{% endif %}
                """))

    def test_is_state(self):
        self.hass.states.set('test.object', 'available')
        self.assertEqual(
            'yes',
            template.render(
                self.hass,
                """
{% if is_state("test.object", "available") %}yes{% else %}no{% endif %}
                """))

    def test_is_state_attr(self):
        self.hass.states.set('test.object', 'available', {'mode': 'on'})
        self.assertEqual(
            'yes',
            template.render(
                self.hass,
                """
{% if is_state_attr("test.object", "mode", "on") %}yes{% else %}no{% endif %}
                """))

    def test_states_function(self):
        self.hass.states.set('test.object', 'available')
        self.assertEqual(
            'available',
            template.render(self.hass, '{{ states("test.object") }}'))
        self.assertEqual(
            'unknown',
            template.render(self.hass, '{{ states("test.object2") }}'))
