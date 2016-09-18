"""The tests for the Template Binary sensor platform."""
import unittest
from unittest import mock

from homeassistant.const import EVENT_STATE_CHANGED, MATCH_ALL
import homeassistant.bootstrap as bootstrap
from homeassistant.components.binary_sensor import template
from homeassistant.exceptions import TemplateError

from tests.common import get_test_home_assistant


class TestBinarySensorTemplate(unittest.TestCase):
    """Test for Binary sensor template platform."""

    @mock.patch.object(template, 'BinarySensorTemplate')
    def test_setup(self, mock_template):
        """"Test the setup."""
        config = {
            'sensors': {
                'test': {
                    'friendly_name': 'virtual thingy',
                    'value_template': '{{ foo }}',
                    'sensor_class': 'motion',
                    'entity_id': 'test'
                },
            }
        }
        hass = mock.MagicMock()
        add_devices = mock.MagicMock()
        result = template.setup_platform(hass, config, add_devices)
        self.assertTrue(result)
        mock_template.assert_called_once_with(hass, 'test', 'virtual thingy',
                                              'motion', '{{ foo }}', 'test')
        add_devices.assert_called_once_with([mock_template.return_value])

    def test_setup_no_sensors(self):
        """"Test setup with no sensors."""
        hass = mock.MagicMock()
        result = bootstrap.setup_component(hass, 'sensor', {
            'sensor': {
                'platform': 'template'
            }
        })
        self.assertFalse(result)

    def test_setup_invalid_device(self):
        """"Test the setup with invalid devices."""
        hass = mock.MagicMock()
        result = bootstrap.setup_component(hass, 'sensor', {
            'sensor': {
                'platform': 'template',
                'sensors': {
                    'foo bar': {},
                },
            }
        })
        self.assertFalse(result)

    def test_setup_invalid_sensor_class(self):
        """"Test setup with invalid sensor class."""
        hass = mock.MagicMock()
        result = bootstrap.setup_component(hass, 'sensor', {
            'sensor': {
                'platform': 'template',
                'sensors': {
                    'test': {
                        'value_template': '{{ foo }}',
                        'sensor_class': 'foobarnotreal',
                    },
                },
            }
        })
        self.assertFalse(result)

    def test_setup_invalid_missing_template(self):
        """"Test setup with invalid and missing template."""
        hass = mock.MagicMock()
        result = bootstrap.setup_component(hass, 'sensor', {
            'sensor': {
                'platform': 'template',
                'sensors': {
                    'test': {
                        'sensor_class': 'motion',
                    },
                }
            }
        })
        self.assertFalse(result)

    def test_attributes(self):
        """"Test the attributes."""
        hass = mock.MagicMock()
        vs = template.BinarySensorTemplate(hass, 'parent', 'Parent',
                                           'motion', '{{ 1 > 1 }}', MATCH_ALL)
        self.assertFalse(vs.should_poll)
        self.assertEqual('motion', vs.sensor_class)
        self.assertEqual('Parent', vs.name)

        vs.update()
        self.assertFalse(vs.is_on)

        vs._template = "{{ 2 > 1 }}"
        vs.update()
        self.assertTrue(vs.is_on)

    def test_event(self):
        """"Test the event."""
        hass = get_test_home_assistant()
        vs = template.BinarySensorTemplate(hass, 'parent', 'Parent',
                                           'motion', '{{ 1 > 1 }}', MATCH_ALL)
        vs.update_ha_state()
        hass.block_till_done()

        with mock.patch.object(vs, 'update') as mock_update:
            hass.bus.fire(EVENT_STATE_CHANGED)
            hass.block_till_done()
            try:
                assert mock_update.call_count == 1
            finally:
                hass.stop()

    @mock.patch('homeassistant.helpers.template.render')
    def test_update_template_error(self, mock_render):
        """"Test the template update error."""
        hass = mock.MagicMock()
        vs = template.BinarySensorTemplate(hass, 'parent', 'Parent',
                                           'motion', '{{ 1 > 1 }}', MATCH_ALL)
        mock_render.side_effect = TemplateError('foo')
        vs.update()
        mock_render.side_effect = TemplateError(
            "UndefinedError: 'None' has no attribute")
        vs.update()
