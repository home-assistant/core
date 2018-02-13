"""The test for the Template sensor platform."""
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant, assert_setup_component


class TestTemplateSensor:
    """Test the Template sensor."""

    hass = None
    # pylint: disable=invalid-name

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_template(self):
        """Test template."""
        with assert_setup_component(1):
            assert setup_component(self.hass, 'sensor', {
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

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('sensor.test_template_sensor')
        assert state.state == 'It .'

        self.hass.states.set('sensor.test_state', 'Works')
        self.hass.block_till_done()
        state = self.hass.states.get('sensor.test_template_sensor')
        assert state.state == 'It Works.'

    def test_icon_template(self):
        """Test icon template."""
        with assert_setup_component(1):
            assert setup_component(self.hass, 'sensor', {
                'sensor': {
                    'platform': 'template',
                    'sensors': {
                        'test_template_sensor': {
                            'value_template': "State",
                            'icon_template':
                                "{% if states.sensor.test_state.state == "
                                "'Works' %}"
                                "mdi:check"
                                "{% endif %}"
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('sensor.test_template_sensor')
        assert state.attributes.get('icon') == ''

        self.hass.states.set('sensor.test_state', 'Works')
        self.hass.block_till_done()
        state = self.hass.states.get('sensor.test_template_sensor')
        assert state.attributes['icon'] == 'mdi:check'

    def test_entity_picture_template(self):
        """Test entity_picture template."""
        with assert_setup_component(1):
            assert setup_component(self.hass, 'sensor', {
                'sensor': {
                    'platform': 'template',
                    'sensors': {
                        'test_template_sensor': {
                            'value_template': "State",
                            'entity_picture_template':
                                "{% if states.sensor.test_state.state == "
                                "'Works' %}"
                                "/local/sensor.png"
                                "{% endif %}"
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('sensor.test_template_sensor')
        assert state.attributes.get('entity_picture') == ''

        self.hass.states.set('sensor.test_state', 'Works')
        self.hass.block_till_done()
        state = self.hass.states.get('sensor.test_template_sensor')
        assert state.attributes['entity_picture'] == '/local/sensor.png'

    def test_friendly_name_template(self):
        """Test friendly_name template."""
        with assert_setup_component(1):
            assert setup_component(self.hass, 'sensor', {
                'sensor': {
                    'platform': 'template',
                    'sensors': {
                        'test_template_sensor': {
                            'value_template': "State",
                            'friendly_name_template':
                                "It {{ states.sensor.test_state.state }}."
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('sensor.test_template_sensor')
        assert state.attributes.get('friendly_name') == 'It .'

        self.hass.states.set('sensor.test_state', 'Works')
        self.hass.block_till_done()
        state = self.hass.states.get('sensor.test_template_sensor')
        assert state.attributes['friendly_name'] == 'It Works.'

    def test_template_syntax_error(self):
        """Test templating syntax error."""
        with assert_setup_component(0):
            assert setup_component(self.hass, 'sensor', {
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

        self.hass.start()
        self.hass.block_till_done()
        assert self.hass.states.all() == []

    def test_template_attribute_missing(self):
        """Test missing attribute template."""
        with assert_setup_component(1):
            assert setup_component(self.hass, 'sensor', {
                'sensor': {
                    'platform': 'template',
                    'sensors': {
                        'test_template_sensor': {
                            'value_template': 'It {{ states.sensor.test_state'
                                              '.attributes.missing }}.'
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('sensor.test_template_sensor')
        assert state.state == 'unknown'

    def test_invalid_name_does_not_create(self):
        """Test invalid name."""
        with assert_setup_component(0):
            assert setup_component(self.hass, 'sensor', {
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

        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_invalid_sensor_does_not_create(self):
        """Test invalid sensor."""
        with assert_setup_component(0):
            assert setup_component(self.hass, 'sensor', {
                'sensor': {
                    'platform': 'template',
                    'sensors': {
                        'test_template_sensor': 'invalid'
                    }
                }
            })

        self.hass.start()

        assert self.hass.states.all() == []

    def test_no_sensors_does_not_create(self):
        """Test no sensors."""
        with assert_setup_component(0):
            assert setup_component(self.hass, 'sensor', {
                'sensor': {
                    'platform': 'template'
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_missing_template_does_not_create(self):
        """Test missing template."""
        with assert_setup_component(0):
            assert setup_component(self.hass, 'sensor', {
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

        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []
