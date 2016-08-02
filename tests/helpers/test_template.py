"""Test Home Assistant template helper methods."""
# pylint: disable=too-many-public-methods
import unittest
from unittest.mock import patch

from homeassistant.components import group
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template
from homeassistant.helpers.unit_system import TYPE_LENGTH
from homeassistant.const import LENGTH_METERS
import homeassistant.util.dt as dt_util

from tests.common import get_test_home_assistant


class TestUtilTemplate(unittest.TestCase):
    """Test the Template."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup the tests."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down stuff we started."""
        self.hass.stop()

    def test_referring_states_by_entity_id(self):
        """."""
        self.hass.states.set('test.object', 'happy')
        self.assertEqual(
            'happy',
            template.render(self.hass, '{{ states.test.object.state }}'))

    def test_iterating_all_states(self):
        """."""
        self.hass.states.set('test.object', 'happy')
        self.hass.states.set('sensor.temperature', 10)

        self.assertEqual(
            '10happy',
            template.render(
                self.hass,
                '{% for state in states %}{{ state.state }}{% endfor %}'))

    def test_iterating_domain_states(self):
        """."""
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

    def test_float(self):
        """."""
        self.hass.states.set('sensor.temperature', '12')

        self.assertEqual(
            '12.0',
            template.render(
                self.hass,
                '{{ float(states.sensor.temperature.state) }}'))

        self.assertEqual(
            'True',
            template.render(
                self.hass,
                '{{ float(states.sensor.temperature.state) > 11 }}'))

    def test_rounding_value(self):
        """."""
        self.hass.states.set('sensor.temperature', 12.78)

        self.assertEqual(
            '12.8',
            template.render(
                self.hass,
                '{{ states.sensor.temperature.state | round(1) }}'))

        self.assertEqual(
            '128',
            template.render(
                self.hass,
                '{{ states.sensor.temperature.state | multiply(10) | round }}'
            ))

    def test_rounding_value_get_original_value_on_error(self):
        """."""
        self.assertEqual(
            'None',
            template.render(
                self.hass,
                '{{ None | round }}'
            ))

        self.assertEqual(
            'no_number',
            template.render(
                self.hass,
                '{{ "no_number" | round }}'
            ))

    def test_multiply(self):
        """."""
        tests = {
            None: 'None',
            10: '100',
            '"abcd"': 'abcd'
        }

        for inp, out in tests.items():
            self.assertEqual(
                out,
                template.render(self.hass,
                                '{{ %s | multiply(10) | round }}' % inp))

    def test_timestamp_local(self):
        """Test the timestamps to local filter."""
        tests = {
            None: 'None',
            1469119144: '2016-07-21 16:39:04',
        }

        for inp, out in tests.items():
            self.assertEqual(
                out,
                template.render(self.hass,
                                '{{ %s | timestamp_local }}' % inp))

    def test_timestamp_utc(self):
        """Test the timestamps to local filter."""
        tests = {
            None: 'None',
            1469119144: '2016-07-21 16:39:04',
            dt_util.as_timestamp(dt_util.utcnow()):
                dt_util.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        for inp, out in tests.items():
            self.assertEqual(
                out,
                template.render(self.hass,
                                '{{ %s | timestamp_utc }}' % inp))

    def test_passing_vars_as_keywords(self):
        """."""
        self.assertEqual(
            '127', template.render(self.hass, '{{ hello }}', hello=127))

    def test_passing_vars_as_vars(self):
        """."""
        self.assertEqual(
            '127', template.render(self.hass, '{{ hello }}', {'hello': 127}))

    def test_render_with_possible_json_value_with_valid_json(self):
        """."""
        self.assertEqual(
            'world',
            template.render_with_possible_json_value(
                self.hass, '{{ value_json.hello }}', '{"hello": "world"}'))

    def test_render_with_possible_json_value_with_invalid_json(self):
        """."""
        self.assertEqual(
            '',
            template.render_with_possible_json_value(
                self.hass, '{{ value_json }}', '{ I AM NOT JSON }'))

    def test_render_with_possible_json_value_with_template_error(self):
        """."""
        self.assertEqual(
            'hello',
            template.render_with_possible_json_value(
                self.hass, '{{ value_json', 'hello'))

    def test_render_with_possible_json_value_with_template_error_value(self):
        """."""
        self.assertEqual(
            '-',
            template.render_with_possible_json_value(
                self.hass, '{{ value_json', 'hello', '-'))

    def test_raise_exception_on_error(self):
        """."""
        with self.assertRaises(TemplateError):
            template.render(self.hass, '{{ invalid_syntax')

    def test_if_state_exists(self):
        """."""
        self.hass.states.set('test.object', 'available')
        self.assertEqual(
            'exists',
            template.render(
                self.hass,
                """
{% if states.test.object %}exists{% else %}not exists{% endif %}
                """))

    def test_is_state(self):
        """."""
        self.hass.states.set('test.object', 'available')
        self.assertEqual(
            'yes',
            template.render(
                self.hass,
                """
{% if is_state("test.object", "available") %}yes{% else %}no{% endif %}
                """))

    def test_is_state_attr(self):
        """."""
        self.hass.states.set('test.object', 'available', {'mode': 'on'})
        self.assertEqual(
            'yes',
            template.render(
                self.hass,
                """
{% if is_state_attr("test.object", "mode", "on") %}yes{% else %}no{% endif %}
                """))

    def test_states_function(self):
        """."""
        self.hass.states.set('test.object', 'available')
        self.assertEqual(
            'available',
            template.render(self.hass, '{{ states("test.object") }}'))
        self.assertEqual(
            'unknown',
            template.render(self.hass, '{{ states("test.object2") }}'))

    @patch('homeassistant.core.dt_util.utcnow', return_value=dt_util.utcnow())
    @patch('homeassistant.helpers.template.TemplateEnvironment.'
           'is_safe_callable', return_value=True)
    def test_now(self, mock_is_safe, mock_utcnow):
        """."""
        self.assertEqual(
            dt_util.utcnow().isoformat(),
            template.render(self.hass, '{{ now.isoformat() }}'))

    @patch('homeassistant.core.dt_util.utcnow', return_value=dt_util.utcnow())
    @patch('homeassistant.helpers.template.TemplateEnvironment.'
           'is_safe_callable', return_value=True)
    def test_utcnow(self, mock_is_safe, mock_utcnow):
        """."""
        self.assertEqual(
            dt_util.utcnow().isoformat(),
            template.render(self.hass, '{{ utcnow.isoformat() }}'))

    def test_utcnow_is_exactly_now(self):
        """."""
        self.assertEqual(
            'True',
            template.render(self.hass, '{{ utcnow == now }}'))

    def test_distance_function_with_1_state(self):
        """."""
        self.hass.config.unit_system[TYPE_LENGTH] = LENGTH_METERS
        self.hass.states.set('test.object', 'happy', {
            'latitude': 32.87336,
            'longitude': -117.22943,
        })

        self.assertEqual(
            '187',
            template.render(
                self.hass, '{{ distance(states.test.object) | round }}'))

    def test_distance_function_with_2_states(self):
        """."""
        self.hass.config.unit_system[TYPE_LENGTH] = LENGTH_METERS
        self.hass.states.set('test.object', 'happy', {
            'latitude': 32.87336,
            'longitude': -117.22943,
        })

        self.hass.states.set('test.object_2', 'happy', {
            'latitude': self.hass.config.latitude,
            'longitude': self.hass.config.longitude,
        })

        self.assertEqual(
            '187',
            template.render(
                self.hass,
                '{{ distance(states.test.object, states.test.object_2)'
                '| round }}'))

    def test_distance_function_with_1_coord(self):
        """."""
        self.hass.config.unit_system[TYPE_LENGTH] = LENGTH_METERS
        self.assertEqual(
            '187',
            template.render(
                self.hass, '{{ distance("32.87336", "-117.22943") | round }}'))

    def test_distance_function_with_2_coords(self):
        """."""
        self.hass.config.unit_system[TYPE_LENGTH] = LENGTH_METERS
        self.assertEqual(
            '187',
            template.render(
                self.hass,
                '{{ distance("32.87336", "-117.22943", %s, %s) | round }}'
                % (self.hass.config.latitude, self.hass.config.longitude)))

    def test_distance_function_with_1_state_1_coord(self):
        """."""
        self.hass.config.unit_system[TYPE_LENGTH] = LENGTH_METERS
        self.hass.states.set('test.object_2', 'happy', {
            'latitude': self.hass.config.latitude,
            'longitude': self.hass.config.longitude,
        })

        self.assertEqual(
            '187',
            template.render(
                self.hass,
                '{{ distance("32.87336", "-117.22943", states.test.object_2) '
                '| round }}'))

        self.assertEqual(
            '187',
            template.render(
                self.hass,
                '{{ distance(states.test.object_2, "32.87336", "-117.22943") '
                '| round }}'))

    def test_distance_function_return_None_if_invalid_state(self):
        """."""
        self.hass.states.set('test.object_2', 'happy', {
            'latitude': 10,
        })

        self.assertEqual(
            'None',
            template.render(
                self.hass,
                '{{ distance(states.test.object_2) | round }}'))

    def test_distance_function_return_None_if_invalid_coord(self):
        """."""
        self.assertEqual(
            'None',
            template.render(
                self.hass,
                '{{ distance("123", "abc") }}'))

        self.assertEqual(
            'None',
            template.render(
                self.hass,
                '{{ distance("123") }}'))

        self.hass.states.set('test.object_2', 'happy', {
            'latitude': self.hass.config.latitude,
            'longitude': self.hass.config.longitude,
        })

        self.assertEqual(
            'None',
            template.render(
                self.hass,
                '{{ distance("123", states.test_object_2) }}'))

    def test_closest_function_home_vs_domain(self):
        """."""
        self.hass.states.set('test_domain.object', 'happy', {
            'latitude': self.hass.config.latitude + 0.1,
            'longitude': self.hass.config.longitude + 0.1,
        })

        self.hass.states.set('not_test_domain.but_closer', 'happy', {
            'latitude': self.hass.config.latitude,
            'longitude': self.hass.config.longitude,
        })

        self.assertEqual(
            'test_domain.object',
            template.render(self.hass,
                            '{{ closest(states.test_domain).entity_id }}'))

    def test_closest_function_home_vs_all_states(self):
        """."""
        self.hass.states.set('test_domain.object', 'happy', {
            'latitude': self.hass.config.latitude + 0.1,
            'longitude': self.hass.config.longitude + 0.1,
        })

        self.hass.states.set('test_domain_2.and_closer', 'happy', {
            'latitude': self.hass.config.latitude,
            'longitude': self.hass.config.longitude,
        })

        self.assertEqual(
            'test_domain_2.and_closer',
            template.render(self.hass,
                            '{{ closest(states).entity_id }}'))

    def test_closest_function_home_vs_group_entity_id(self):
        """."""
        self.hass.states.set('test_domain.object', 'happy', {
            'latitude': self.hass.config.latitude + 0.1,
            'longitude': self.hass.config.longitude + 0.1,
        })

        self.hass.states.set('not_in_group.but_closer', 'happy', {
            'latitude': self.hass.config.latitude,
            'longitude': self.hass.config.longitude,
        })

        group.Group(self.hass, 'location group', ['test_domain.object'])

        self.assertEqual(
            'test_domain.object',
            template.render(self.hass,
                            '{{ closest("group.location_group").entity_id }}'))

    def test_closest_function_home_vs_group_state(self):
        """."""
        self.hass.states.set('test_domain.object', 'happy', {
            'latitude': self.hass.config.latitude + 0.1,
            'longitude': self.hass.config.longitude + 0.1,
        })

        self.hass.states.set('not_in_group.but_closer', 'happy', {
            'latitude': self.hass.config.latitude,
            'longitude': self.hass.config.longitude,
        })

        group.Group(self.hass, 'location group', ['test_domain.object'])

        self.assertEqual(
            'test_domain.object',
            template.render(
                self.hass,
                '{{ closest(states.group.location_group).entity_id }}'))

    def test_closest_function_to_coord(self):
        """."""
        self.hass.states.set('test_domain.closest_home', 'happy', {
            'latitude': self.hass.config.latitude + 0.1,
            'longitude': self.hass.config.longitude + 0.1,
        })

        self.hass.states.set('test_domain.closest_zone', 'happy', {
            'latitude': self.hass.config.latitude + 0.2,
            'longitude': self.hass.config.longitude + 0.2,
        })

        self.hass.states.set('zone.far_away', 'zoning', {
            'latitude': self.hass.config.latitude + 0.3,
            'longitude': self.hass.config.longitude + 0.3,
        })

        self.assertEqual(
            'test_domain.closest_zone',
            template.render(
                self.hass,
                '{{ closest("%s", %s, states.test_domain).entity_id }}'
                % (self.hass.config.latitude + 0.3,
                   self.hass.config.longitude + 0.3))
        )

    def test_closest_function_to_entity_id(self):
        """."""
        self.hass.states.set('test_domain.closest_home', 'happy', {
            'latitude': self.hass.config.latitude + 0.1,
            'longitude': self.hass.config.longitude + 0.1,
        })

        self.hass.states.set('test_domain.closest_zone', 'happy', {
            'latitude': self.hass.config.latitude + 0.2,
            'longitude': self.hass.config.longitude + 0.2,
        })

        self.hass.states.set('zone.far_away', 'zoning', {
            'latitude': self.hass.config.latitude + 0.3,
            'longitude': self.hass.config.longitude + 0.3,
        })

        self.assertEqual(
            'test_domain.closest_zone',
            template.render(
                self.hass,
                '{{ closest("zone.far_away", states.test_domain).entity_id }}')
        )

    def test_closest_function_to_state(self):
        """."""
        self.hass.states.set('test_domain.closest_home', 'happy', {
            'latitude': self.hass.config.latitude + 0.1,
            'longitude': self.hass.config.longitude + 0.1,
        })

        self.hass.states.set('test_domain.closest_zone', 'happy', {
            'latitude': self.hass.config.latitude + 0.2,
            'longitude': self.hass.config.longitude + 0.2,
        })

        self.hass.states.set('zone.far_away', 'zoning', {
            'latitude': self.hass.config.latitude + 0.3,
            'longitude': self.hass.config.longitude + 0.3,
        })

        self.assertEqual(
            'test_domain.closest_zone',
            template.render(
                self.hass,
                '{{ closest(states.zone.far_away, '
                'states.test_domain).entity_id }}')
        )

    def test_closest_function_invalid_state(self):
        """."""
        self.hass.states.set('test_domain.closest_home', 'happy', {
            'latitude': self.hass.config.latitude + 0.1,
            'longitude': self.hass.config.longitude + 0.1,
        })

        for state in ('states.zone.non_existing', '"zone.non_existing"'):
            self.assertEqual(
                'None',
                template.render(
                    self.hass, '{{ closest(%s, states) }}' % state))

    def test_closest_function_state_with_invalid_location(self):
        """."""
        self.hass.states.set('test_domain.closest_home', 'happy', {
            'latitude': 'invalid latitude',
            'longitude': self.hass.config.longitude + 0.1,
        })

        self.assertEqual(
            'None',
            template.render(
                self.hass,
                '{{ closest(states.test_domain.closest_home, '
                'states) }}'))

    def test_closest_function_invalid_coordinates(self):
        """."""
        self.hass.states.set('test_domain.closest_home', 'happy', {
            'latitude': self.hass.config.latitude + 0.1,
            'longitude': self.hass.config.longitude + 0.1,
        })

        self.assertEqual(
            'None',
            template.render(self.hass,
                            '{{ closest("invalid", "coord", states) }}'))

    def test_closest_function_no_location_states(self):
        """."""
        self.assertEqual('None',
                         template.render(self.hass, '{{ closest(states) }}'))
