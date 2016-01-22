"""
tests.components.sensor.template
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests template sensor.
"""
from unittest.mock import patch

import pytest

import homeassistant.core as ha
import homeassistant.components.sensor as sensor


class TestTemplateSensor:
    """ Test the Template sensor. """

    def setup_method(self, method):
        self.hass = ha.HomeAssistant()

    def teardown_method(self, method):
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_template(self):
        assert sensor.setup(self.hass, {
            'sensor': {
                'platform': 'template',
                'sensors': {
                    'test_template_sensor': {
                        'value_template':
                            "{{ states.sensor.test_state.state }}"
                    }
                }
            }
        })

        state = self.hass.states.get('sensor.test_template_sensor')
        assert state.state == ''

        self.hass.states.set('sensor.test_state', 'Works')
        self.hass.pool.block_till_done()
        state = self.hass.states.get('sensor.test_template_sensor')
        assert state.state == 'Works'

    def test_template_syntax_error(self):
        assert sensor.setup(self.hass, {
            'sensor': {
                'platform': 'template',
                'sensors': {
                    'test_template_sensor': {
                        'value_template':
                            "{% if rubbish %}"
                    }
                }
            }
        })


        self.hass.states.set('sensor.test_state', 'Works')
        self.hass.pool.block_till_done()
        state = self.hass.states.get('sensor.test_template_sensor')
        assert state.state == 'error'
