"""The test for the Template sensor platform."""
import homeassistant.components.sensor as sensor

from tests.common import get_test_home_assistant


class TestTemplateSensor:
    """Test the Template sensor."""

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_template(self):
        """Test template."""
        assert sensor.setup(self.hass, {
            'sensor': {
                'platform': 'template',
                'sensors': {
                    'test_template_sensor': {
                        'value_template':
                            "It {{ states.sensor.test_state.state }}."
                    }
                }
            }
        })

        state = self.hass.states.get('sensor.test_template_sensor')
        assert state.state == 'It .'

        self.hass.states.set('sensor.test_state', 'Works')
        self.hass.pool.block_till_done()
        state = self.hass.states.get('sensor.test_template_sensor')
        assert state.state == 'It Works.'

    def test_template_syntax_error(self):
        """Test templating syntax error."""
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

    def test_template_attribute_missing(self):
        """Test missing attribute template."""
        assert sensor.setup(self.hass, {
            'sensor': {
                'platform': 'template',
                'sensors': {
                    'test_template_sensor': {
                        'value_template':
                        "It {{ states.sensor.test_state.attributes.missing }}."
                    }
                }
            }
        })

        state = self.hass.states.get('sensor.test_template_sensor')
        assert state.state == 'error'

    def test_invalid_name_does_not_create(self):
        """Test invalid name."""
        assert sensor.setup(self.hass, {
            'sensor': {
                'platform': 'template',
                'sensors': {
                    'test INVALID sensor': {
                        'value_template':
                            "{{ states.sensor.test_state.state }}"
                    }
                }
            }
        })
        assert self.hass.states.all() == []

    def test_invalid_sensor_does_not_create(self):
        """Test invalid sensor."""
        assert sensor.setup(self.hass, {
            'sensor': {
                'platform': 'template',
                'sensors': {
                    'test_template_sensor': 'invalid'
                }
            }
        })
        assert self.hass.states.all() == []

    def test_no_sensors_does_not_create(self):
        """Test no sensors."""
        assert sensor.setup(self.hass, {
            'sensor': {
                'platform': 'template'
            }
        })
        assert self.hass.states.all() == []

    def test_missing_template_does_not_create(self):
        """Test missing template."""
        assert sensor.setup(self.hass, {
            'sensor': {
                'platform': 'template',
                'sensors': {
                    'test_template_sensor': {
                        'not_value_template':
                            "{{ states.sensor.test_state.state }}"
                    }
                }
            }
        })
        assert self.hass.states.all() == []
