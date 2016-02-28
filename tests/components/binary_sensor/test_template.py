"""
tests.components.binary_sensor.test_template
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tests for template binary_sensor.
"""

import unittest
from unittest import mock

from homeassistant.components.binary_sensor import template
from homeassistant.exceptions import TemplateError


class TestBinarySensorTemplate(unittest.TestCase):
    @mock.patch.object(template, 'BinarySensorTemplate')
    def test_setup(self, mock_template):
        config = {
            'sensors': {
                'test': {
                    'friendly_name': 'virtual thingy',
                    'value_template': '{{ foo }}',
                    'sensor_class': 'motion',
                },
            }
        }
        hass = mock.MagicMock()
        add_devices = mock.MagicMock()
        result = template.setup_platform(hass, config, add_devices)
        self.assertTrue(result)
        mock_template.assert_called_once_with(hass, 'test', 'virtual thingy',
                                              'motion', '{{ foo }}')
        add_devices.assert_called_once_with([mock_template.return_value])

    def test_setup_no_sensors(self):
        config = {}
        result = template.setup_platform(None, config, None)
        self.assertFalse(result)

    def test_setup_invalid_device(self):
        config = {
            'sensors': {
                'foo bar': {},
            },
        }
        result = template.setup_platform(None, config, None)
        self.assertFalse(result)

    def test_setup_invalid_sensor_class(self):
        config = {
            'sensors': {
                'test': {
                    'value_template': '{{ foo }}',
                    'sensor_class': 'foobarnotreal',
                },
            },
        }
        result = template.setup_platform(None, config, None)
        self.assertFalse(result)

    def test_setup_invalid_missing_template(self):
        config = {
            'sensors': {
                'test': {
                    'sensor_class': 'motion',
                },
            },
        }
        result = template.setup_platform(None, config, None)
        self.assertFalse(result)

    def test_attributes(self):
        hass = mock.MagicMock()
        vs = template.BinarySensorTemplate(hass, 'parent', 'Parent',
                                           'motion', '{{ 1 > 1 }}')
        self.assertFalse(vs.should_poll)
        self.assertEqual('motion', vs.sensor_class)
        self.assertEqual('Parent', vs.name)

        vs.update()
        self.assertFalse(vs.is_on)

        vs._template = "{{ 2 > 1 }}"
        vs.update()
        self.assertTrue(vs.is_on)

    def test_event(self):
        hass = mock.MagicMock()
        vs = template.BinarySensorTemplate(hass, 'parent', 'Parent',
                                           'motion', '{{ 1 > 1 }}')
        with mock.patch.object(vs, 'update_ha_state') as mock_update:
            vs._event_listener(None)
            mock_update.assert_called_once_with(True)

    def test_update(self):
        hass = mock.MagicMock()
        vs = template.BinarySensorTemplate(hass, 'parent', 'Parent',
                                           'motion', '{{ 2 > 1 }}')
        self.assertEqual(None, vs._state)
        vs.update()
        self.assertTrue(vs._state)

    @mock.patch('homeassistant.helpers.template.render')
    def test_update_template_error(self, mock_render):
        hass = mock.MagicMock()
        vs = template.BinarySensorTemplate(hass, 'parent', 'Parent',
                                           'motion', '{{ 1 > 1 }}')
        mock_render.side_effect = TemplateError('foo')
        vs.update()
        mock_render.side_effect = TemplateError(
            "UndefinedError: 'None' has no attribute")
        vs.update()
