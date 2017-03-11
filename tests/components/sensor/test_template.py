"""The test for the Template sensor platform."""
import asyncio

from homeassistant.core import CoreState, State
from homeassistant.setup import setup_component, async_setup_component
from homeassistant.helpers.restore_state import DATA_RESTORE_CACHE

from tests.common import (
    get_test_home_assistant, assert_setup_component, mock_component)


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
        assert 'icon' not in state.attributes

        self.hass.states.set('sensor.test_state', 'Works')
        self.hass.block_till_done()
        state = self.hass.states.get('sensor.test_template_sensor')
        assert state.attributes['icon'] == 'mdi:check'

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


@asyncio.coroutine
def test_restore_state(hass):
    """Ensure states are restored on startup."""
    hass.data[DATA_RESTORE_CACHE] = {
        'sensor.test_template_sensor':
            State('sensor.test_template_sensor', 'It Test.'),
    }

    hass.state = CoreState.starting
    mock_component(hass, 'recorder')

    yield from async_setup_component(hass, 'sensor', {
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

    state = hass.states.get('sensor.test_template_sensor')
    assert state.state == 'It Test.'

    yield from hass.async_start()
    yield from hass.async_block_till_done()

    state = hass.states.get('sensor.test_template_sensor')
    assert state.state == 'It .'
