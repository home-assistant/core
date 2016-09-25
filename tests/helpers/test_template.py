"""Test Home Assistant template helper methods."""
# pylint: disable=too-many-public-methods
import unittest
from unittest.mock import patch

from homeassistant.components import group
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template
from homeassistant.util.unit_system import UnitSystem
from homeassistant.const import (
    LENGTH_METERS,
    TEMP_CELSIUS,
    MASS_GRAMS,
    VOLUME_LITERS,
)
import homeassistant.util.dt as dt_util

from tests.common import get_test_home_assistant


class TestUtilTemplate(unittest.TestCase):
    """Test the Template."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup the tests."""
        self.hass = get_test_home_assistant()
        self.hass.config.units = UnitSystem('custom', TEMP_CELSIUS,
                                            LENGTH_METERS, VOLUME_LITERS,
                                            MASS_GRAMS)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down stuff we started."""
        self.hass.stop()

    def test_referring_states_by_entity_id(self):
        """Test referring states by entity id."""
        self.hass.states.set('test.object', 'happy')
        self.assertEqual(
            'happy',
            template.render(self.hass, '{{ states.test.object.state }}'))

    def test_iterating_all_states(self):
        """Test iterating all states."""
        self.hass.states.set('test.object', 'happy')
        self.hass.states.set('sensor.temperature', 10)

        self.assertEqual(
            '10happy',
            template.render(
                self.hass,
                '{% for state in states %}{{ state.state }}{% endfor %}'))

    def test_iterating_domain_states(self):
        """Test iterating domain states."""
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
        """Test float."""
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
        """Test rounding value."""
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
        """Test rounding value get original value on error."""
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
        """Test multiply."""
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

    def test_timestamp_custom(self):
        """Test the timestamps to custom filter."""
        tests = [
            (None, None, None, 'None'),
            (1469119144, None, True, '2016-07-21 16:39:04'),
            (1469119144, '%Y', True, '2016'),
            (1469119144, 'invalid', True, 'invalid'),
            (dt_util.as_timestamp(dt_util.utcnow()), None, False,
                dt_util.now().strftime('%Y-%m-%d %H:%M:%S'))
        ]

        for inp, fmt, local, out in tests:
            if fmt:
                fil = 'timestamp_custom(\'{}\')'.format(fmt)
            elif fmt and local:
                fil = 'timestamp_custom(\'{0}\', {1})'.format(fmt, local)
            else:
                fil = 'timestamp_custom'

            self.assertEqual(
                    out,
                    template.render(self.hass, '{{ %s | %s }}' % (inp, fil))
                )

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
        """Test passing variables as keywords."""
        self.assertEqual(
            '127', template.render(self.hass, '{{ hello }}', hello=127))

    def test_passing_vars_as_vars(self):
        """Test passing variables as variables."""
        self.assertEqual(
            '127', template.render(self.hass, '{{ hello }}', {'hello': 127}))

    def test_render_with_possible_json_value_with_valid_json(self):
        """Render with possible JSON value with valid JSON."""
        self.assertEqual(
            'world',
            template.render_with_possible_json_value(
                self.hass, '{{ value_json.hello }}', '{"hello": "world"}'))

    def test_render_with_possible_json_value_with_invalid_json(self):
        """Render with possible JSON value with invalid JSON."""
        self.assertEqual(
            '',
            template.render_with_possible_json_value(
                self.hass, '{{ value_json }}', '{ I AM NOT JSON }'))

    def test_render_with_possible_json_value_with_template_error(self):
        """Render with possible JSON value with template error."""
        self.assertEqual(
            'hello',
            template.render_with_possible_json_value(
                self.hass, '{{ value_json', 'hello'))

    def test_render_with_possible_json_value_with_template_error_value(self):
        """Render with possible JSON value with template error value."""
        self.assertEqual(
            '-',
            template.render_with_possible_json_value(
                self.hass, '{{ value_json', 'hello', '-'))

    def test_raise_exception_on_error(self):
        """Test raising an exception on error."""
        with self.assertRaises(TemplateError):
            template.render(self.hass, '{{ invalid_syntax')

    def test_if_state_exists(self):
        """Test if state exists works."""
        self.hass.states.set('test.object', 'available')
        self.assertEqual(
            'exists',
            template.render(
                self.hass,
                """
{% if states.test.object %}exists{% else %}not exists{% endif %}
                """))

    def test_is_state(self):
        """Test is_state method."""
        self.hass.states.set('test.object', 'available')
        self.assertEqual(
            'yes',
            template.render(
                self.hass,
                """
{% if is_state("test.object", "available") %}yes{% else %}no{% endif %}
                """))

    def test_is_state_attr(self):
        """Test is_state_attr method."""
        self.hass.states.set('test.object', 'available', {'mode': 'on'})
        self.assertEqual(
            'yes',
            template.render(
                self.hass,
                """
{% if is_state_attr("test.object", "mode", "on") %}yes{% else %}no{% endif %}
                """))

    def test_states_function(self):
        """Test using states as a function."""
        self.hass.states.set('test.object', 'available')
        self.assertEqual(
            'available',
            template.render(self.hass, '{{ states("test.object") }}'))
        self.assertEqual(
            'unknown',
            template.render(self.hass, '{{ states("test.object2") }}'))

    @patch('homeassistant.core.dt_util.now', return_value=dt_util.now())
    @patch('homeassistant.helpers.template.TemplateEnvironment.'
           'is_safe_callable', return_value=True)
    def test_now(self, mock_is_safe, mock_utcnow):
        """Test now method."""
        self.assertEqual(
            dt_util.now().isoformat(),
            template.render(self.hass, '{{ now().isoformat() }}'))

    @patch('homeassistant.core.dt_util.utcnow', return_value=dt_util.utcnow())
    @patch('homeassistant.helpers.template.TemplateEnvironment.'
           'is_safe_callable', return_value=True)
    def test_utcnow(self, mock_is_safe, mock_utcnow):
        """Test utcnow method."""
        self.assertEqual(
            dt_util.utcnow().isoformat(),
            template.render(self.hass, '{{ utcnow().isoformat() }}'))

    def test_distance_function_with_1_state(self):
        """Test distance function with 1 state."""
        self.hass.states.set('test.object', 'happy', {
            'latitude': 32.87336,
            'longitude': -117.22943,
        })

        self.assertEqual(
            '187',
            template.render(
                self.hass, '{{ distance(states.test.object) | round }}'))

    def test_distance_function_with_2_states(self):
        """Test distance function with 2 states."""
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
        """Test distance function with 1 coord."""
        self.assertEqual(
            '187',
            template.render(
                self.hass, '{{ distance("32.87336", "-117.22943") | round }}'))

    def test_distance_function_with_2_coords(self):
        """Test distance function with 2 coords."""
        self.assertEqual(
            '187',
            template.render(
                self.hass,
                '{{ distance("32.87336", "-117.22943", %s, %s) | round }}'
                % (self.hass.config.latitude, self.hass.config.longitude)))

    def test_distance_function_with_1_state_1_coord(self):
        """Test distance function with 1 state 1 coord."""
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
        """Test distance function return None if invalid state."""
        self.hass.states.set('test.object_2', 'happy', {
            'latitude': 10,
        })

        self.assertEqual(
            'None',
            template.render(
                self.hass,
                '{{ distance(states.test.object_2) | round }}'))

    def test_distance_function_return_None_if_invalid_coord(self):
        """Test distance function return None if invalid coord."""
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
        """Test closest function home vs domain."""
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
        """Test closest function home vs all states."""
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
        """Test closest function home vs group entity id."""
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
        """Test closest function home vs group state."""
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
        """Test closest function to coord."""
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
        """Test closest function to entity id."""
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
        """Test closest function to state."""
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
        """Test closest function invalid state."""
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
        """Test closest function state with invalid location."""
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
        """Test closest function invalid coordinates."""
        self.hass.states.set('test_domain.closest_home', 'happy', {
            'latitude': self.hass.config.latitude + 0.1,
            'longitude': self.hass.config.longitude + 0.1,
        })

        self.assertEqual(
            'None',
            template.render(self.hass,
                            '{{ closest("invalid", "coord", states) }}'))

    def test_closest_function_no_location_states(self):
        """Test closest function without location states."""
        self.assertEqual('None',
                         template.render(self.hass, '{{ closest(states) }}'))

    def test_compiling_template(self):
        """Test compiling a template."""
        self.hass.states.set('test_domain.hello', 'world')
        compiled = template.compile_template(
            self.hass, '{{ states.test_domain.hello.state }}')

        with patch('homeassistant.helpers.template.compile_template',
                   side_effect=Exception('Should not be called')):
            assert 'world' == template.render(self.hass, compiled)
