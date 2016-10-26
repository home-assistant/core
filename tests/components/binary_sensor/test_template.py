"""The tests for the Template Binary sensor platform."""
import unittest
from unittest import mock

from homeassistant.const import EVENT_STATE_CHANGED, MATCH_ALL
import homeassistant.bootstrap as bootstrap
from homeassistant.components.binary_sensor import template
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template as template_hlpr
from homeassistant.util.async import run_callback_threadsafe

from tests.common import get_test_home_assistant, assert_setup_component


class TestBinarySensorTemplate(unittest.TestCase):
    """Test for Binary sensor template platform."""

    hass = None
    # pylint: disable=invalid-name

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    @mock.patch.object(template, 'BinarySensorTemplate')
    def test_setup(self, mock_template):
        """"Test the setup."""
        config = {
            'binary_sensor': {
                'platform': 'template',
                'sensors': {
                    'test': {
                        'friendly_name': 'virtual thingy',
                        'value_template': '{{ foo }}',
                        'sensor_class': 'motion',
                    },
                },
            },
        }
        with assert_setup_component(1):
            assert bootstrap.setup_component(
                self.hass, 'binary_sensor', config)

    def test_setup_no_sensors(self):
        """"Test setup with no sensors."""
        with assert_setup_component(0):
            assert bootstrap.setup_component(self.hass, 'binary_sensor', {
                'binary_sensor': {
                    'platform': 'template'
                }
            })

    def test_setup_invalid_device(self):
        """"Test the setup with invalid devices."""
        with assert_setup_component(0):
            assert bootstrap.setup_component(self.hass, 'binary_sensor', {
                'binary_sensor': {
                    'platform': 'template',
                    'sensors': {
                        'foo bar': {},
                    },
                }
            })

    def test_setup_invalid_sensor_class(self):
        """"Test setup with invalid sensor class."""
        with assert_setup_component(0):
            assert bootstrap.setup_component(self.hass, 'binary_sensor', {
                'binary_sensor': {
                    'platform': 'template',
                    'sensors': {
                        'test': {
                            'value_template': '{{ foo }}',
                            'sensor_class': 'foobarnotreal',
                        },
                    },
                }
            })

    def test_setup_invalid_missing_template(self):
        """"Test setup with invalid and missing template."""
        with assert_setup_component(0):
            assert bootstrap.setup_component(self.hass, 'binary_sensor', {
                'binary_sensor': {
                    'platform': 'template',
                    'sensors': {
                        'test': {
                            'sensor_class': 'motion',
                        },
                    }
                }
            })

    def test_attributes(self):
        """"Test the attributes."""
        vs = run_callback_threadsafe(
            self.hass.loop, template.BinarySensorTemplate,
            self.hass, 'parent', 'Parent', 'motion',
            template_hlpr.Template('{{ 1 > 1 }}', self.hass), MATCH_ALL
        ).result()
        self.assertFalse(vs.should_poll)
        self.assertEqual('motion', vs.sensor_class)
        self.assertEqual('Parent', vs.name)

        vs.update()
        self.assertFalse(vs.is_on)

        # pylint: disable=protected-access
        vs._template = template_hlpr.Template("{{ 2 > 1 }}", self.hass)

        vs.update()
        self.assertTrue(vs.is_on)

    def test_event(self):
        """"Test the event."""
        vs = run_callback_threadsafe(
            self.hass.loop, template.BinarySensorTemplate,
            self.hass, 'parent', 'Parent', 'motion',
            template_hlpr.Template('{{ 1 > 1 }}', self.hass), MATCH_ALL
        ).result()
        vs.update_ha_state()
        self.hass.block_till_done()

        with mock.patch.object(vs, 'async_update') as mock_update:
            self.hass.bus.fire(EVENT_STATE_CHANGED)
            self.hass.block_till_done()
            assert mock_update.call_count == 1

    @mock.patch('homeassistant.helpers.template.Template.render')
    def test_update_template_error(self, mock_render):
        """"Test the template update error."""
        vs = run_callback_threadsafe(
            self.hass.loop, template.BinarySensorTemplate,
            self.hass, 'parent', 'Parent', 'motion',
            template_hlpr.Template('{{ 1 > 1 }}', self.hass), MATCH_ALL
        ).result()
        mock_render.side_effect = TemplateError('foo')
        vs.update()
        mock_render.side_effect = TemplateError(
            "UndefinedError: 'None' has no attribute")
        vs.update()
