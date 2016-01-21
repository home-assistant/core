"""
tests.components.sensor.template
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests template sensor.
"""
from unittest.mock import patch

import pytest

import homeassistant.core as ha
import homeassistant.components.sensor as sensor


@pytest.mark.usefixtures('betamax_session')
class TestSensorYr:
    """ Test the Yr sensor. """

    def setup_method(self, method):
        self.hass = ha.HomeAssistant()
        self.hass.config.latitude = 32.87336
        self.hass.config.longitude = 117.22743

    def teardown_method(self, method):
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_template(self, betamax_session):
        with patch('homeassistant.components.sensor.yr.requests.Session',
                   return_value=betamax_session):
            assert sensor.setup(self.hass, {
                'sensor': {
                    'platform': 'template',
                    'sensors': {
                        'test_template_sensor': {
                            'value_template':
                                '{{ states.sensor.test_state.state }}'
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
