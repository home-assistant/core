"""The tests for the Template Binary sensor platform."""
from datetime import timedelta
import unittest
from unittest import mock

from homeassistant import setup
from homeassistant.components.template import binary_sensor as template
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template as template_hlpr
from homeassistant.util.async_ import run_callback_threadsafe
import homeassistant.util.dt as dt_util

from tests.common import (
    get_test_home_assistant, assert_setup_component, async_fire_time_changed)


class TestBinarySensorTemplate(unittest.TestCase):
    """Test for Binary sensor template platform."""

    hass = None
    # pylint: disable=invalid-name

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup(self):
        """Test the setup."""
        config = {
            'binary_sensor': {
                'platform': 'template',
                'sensors': {
                    'test': {
                        'friendly_name': 'virtual thingy',
                        'value_template': '{{ foo }}',
                        'device_class': 'motion',
                    },
                },
            },
        }
        with assert_setup_component(1):
            assert setup.setup_component(
                self.hass, 'binary_sensor', config)

    def test_setup_no_sensors(self):
        """Test setup with no sensors."""
        with assert_setup_component(0):
            assert setup.setup_component(self.hass, 'binary_sensor', {
                'binary_sensor': {
                    'platform': 'template'
                }
            })

    def test_setup_invalid_device(self):
        """Test the setup with invalid devices."""
        with assert_setup_component(0):
            assert setup.setup_component(self.hass, 'binary_sensor', {
                'binary_sensor': {
                    'platform': 'template',
                    'sensors': {
                        'foo bar': {},
                    },
                }
            })

    def test_setup_invalid_device_class(self):
        """Test setup with invalid sensor class."""
        with assert_setup_component(0):
            assert setup.setup_component(self.hass, 'binary_sensor', {
                'binary_sensor': {
                    'platform': 'template',
                    'sensors': {
                        'test': {
                            'value_template': '{{ foo }}',
                            'device_class': 'foobarnotreal',
                        },
                    },
                }
            })

    def test_setup_invalid_missing_template(self):
        """Test setup with invalid and missing template."""
        with assert_setup_component(0):
            assert setup.setup_component(self.hass, 'binary_sensor', {
                'binary_sensor': {
                    'platform': 'template',
                    'sensors': {
                        'test': {
                            'device_class': 'motion',
                        },
                    }
                }
            })

    def test_icon_template(self):
        """Test icon template."""
        with assert_setup_component(1):
            assert setup.setup_component(self.hass, 'binary_sensor', {
                'binary_sensor': {
                    'platform': 'template',
                    'sensors': {
                        'test_template_sensor': {
                            'value_template': "{{ states.sensor.xyz.state }}",
                            'icon_template':
                                "{% if "
                                "states.binary_sensor.test_state.state == "
                                "'Works' %}"
                                "mdi:check"
                                "{% endif %}"
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_template_sensor')
        assert state.attributes.get('icon') == ''

        self.hass.states.set('binary_sensor.test_state', 'Works')
        self.hass.block_till_done()
        state = self.hass.states.get('binary_sensor.test_template_sensor')
        assert state.attributes['icon'] == 'mdi:check'

    def test_entity_picture_template(self):
        """Test entity_picture template."""
        with assert_setup_component(1):
            assert setup.setup_component(self.hass, 'binary_sensor', {
                'binary_sensor': {
                    'platform': 'template',
                    'sensors': {
                        'test_template_sensor': {
                            'value_template': "{{ states.sensor.xyz.state }}",
                            'entity_picture_template':
                                "{% if "
                                "states.binary_sensor.test_state.state == "
                                "'Works' %}"
                                "/local/sensor.png"
                                "{% endif %}"
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test_template_sensor')
        assert state.attributes.get('entity_picture') == ''

        self.hass.states.set('binary_sensor.test_state', 'Works')
        self.hass.block_till_done()
        state = self.hass.states.get('binary_sensor.test_template_sensor')
        assert state.attributes['entity_picture'] == '/local/sensor.png'

    @mock.patch('homeassistant.components.template.binary_sensor.'
                'BinarySensorTemplate._update_state')
    def test_match_all(self, _update_state):
        """Test template that is rerendered on any state lifecycle."""
        with assert_setup_component(1):
            assert setup.setup_component(self.hass, 'binary_sensor', {
                'binary_sensor': {
                    'platform': 'template',
                    'sensors': {
                        'match_all_template_sensor': {
                            'value_template': (
                                "{% for state in states %}"
                                "{% if state.entity_id == 'sensor.humidity' %}"
                                "{{ state.entity_id }}={{ state.state }}"
                                "{% endif %}"
                                "{% endfor %}"),
                        },
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()
        init_calls = len(_update_state.mock_calls)

        self.hass.states.set('sensor.any_state', 'update')
        self.hass.block_till_done()
        assert len(_update_state.mock_calls) == init_calls

    def test_attributes(self):
        """Test the attributes."""
        vs = run_callback_threadsafe(
            self.hass.loop, template.BinarySensorTemplate,
            self.hass, 'parent', 'Parent', 'motion',
            template_hlpr.Template('{{ 1 > 1 }}', self.hass),
            None, None, None, None
        ).result()
        assert not vs.should_poll
        assert vs.device_class == 'motion'
        assert vs.name == 'Parent'

        assert not vs.is_on

    def test_state_clone(self):
        """Test using the state directly."""
        config = {
            'binary_sensor': {
                'platform': 'template',
                'sensors': {
                    'test': {
                        'friendly_name': 'virtual thingy',
                        'value_template':
                            "{{ states.sensor.test_state.state }}",
                        'device_class': 'motion',
                    },
                },
            },
        }
        with assert_setup_component(1):
            assert setup.setup_component(
                self.hass, 'binary_sensor', config)

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test')
        assert state.state == 'off'

        self.hass.states.set('sensor.test_state', 'on')
        self.hass.block_till_done()

        state = self.hass.states.get('binary_sensor.test')
        assert state.state == 'on'

    @mock.patch('homeassistant.components.template.binary_sensor.'
                'BinarySensorTemplate._template_error')
    def test_update_template_error(self, _template_error):
        """Test the template update error."""
        vs = run_callback_threadsafe(
            self.hass.loop, template.BinarySensorTemplate,
            self.hass, 'parent', 'Parent', 'motion',
            template_hlpr.Template('{{ 1 > 1 }}', self.hass),
            None, None, None, None
        ).result()

        # pylint: disable=protected-access
        run_callback_threadsafe(
            self.hass.loop, vs._update_state,
            TemplateError('foo')).result()
        assert vs._state is None
        assert len(_template_error.mock_calls) == 1

        run_callback_threadsafe(
            self.hass.loop, vs._update_state, 'on').result()
        assert vs._state is True
        assert len(_template_error.mock_calls) == 1

        run_callback_threadsafe(
            self.hass.loop, vs._update_state, TemplateError(
                "UndefinedError: 'None' has no attribute")).result()
        assert vs._state is None
        assert len(_template_error.mock_calls) == 2


async def test_template_delay_on(hass):
    """Test binary sensor template delay on."""
    config = {
        'binary_sensor': {
            'platform': 'template',
            'sensors': {
                'test': {
                    'friendly_name': 'virtual thingy',
                    'value_template':
                        "{{ states.sensor.test_state.state == 'on' }}",
                    'device_class': 'motion',
                    'delay_on': 5
                },
            },
        },
    }
    await setup.async_setup_component(hass, 'binary_sensor', config)
    await hass.async_start()

    hass.states.async_set('sensor.test_state', 'on')
    await hass.async_block_till_done()

    state = hass.states.get('binary_sensor.test')
    assert state.state == 'off'

    future = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get('binary_sensor.test')
    assert state.state == 'on'

    # check with time changes
    hass.states.async_set('sensor.test_state', 'off')
    await hass.async_block_till_done()

    state = hass.states.get('binary_sensor.test')
    assert state.state == 'off'

    hass.states.async_set('sensor.test_state', 'on')
    await hass.async_block_till_done()

    state = hass.states.get('binary_sensor.test')
    assert state.state == 'off'

    hass.states.async_set('sensor.test_state', 'off')
    await hass.async_block_till_done()

    state = hass.states.get('binary_sensor.test')
    assert state.state == 'off'

    future = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get('binary_sensor.test')
    assert state.state == 'off'


async def test_template_delay_off(hass):
    """Test binary sensor template delay off."""
    config = {
        'binary_sensor': {
            'platform': 'template',
            'sensors': {
                'test': {
                    'friendly_name': 'virtual thingy',
                    'value_template':
                        "{{ states.sensor.test_state.state == 'on' }}",
                    'device_class': 'motion',
                    'delay_off': 5
                },
            },
        },
    }
    hass.states.async_set('sensor.test_state', 'on')
    await setup.async_setup_component(hass, 'binary_sensor', config)
    await hass.async_start()

    hass.states.async_set('sensor.test_state', 'off')
    await hass.async_block_till_done()

    state = hass.states.get('binary_sensor.test')
    assert state.state == 'on'

    future = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get('binary_sensor.test')
    assert state.state == 'off'

    # check with time changes
    hass.states.async_set('sensor.test_state', 'on')
    await hass.async_block_till_done()

    state = hass.states.get('binary_sensor.test')
    assert state.state == 'on'

    hass.states.async_set('sensor.test_state', 'off')
    await hass.async_block_till_done()

    state = hass.states.get('binary_sensor.test')
    assert state.state == 'on'

    hass.states.async_set('sensor.test_state', 'on')
    await hass.async_block_till_done()

    state = hass.states.get('binary_sensor.test')
    assert state.state == 'on'

    future = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get('binary_sensor.test')
    assert state.state == 'on'
