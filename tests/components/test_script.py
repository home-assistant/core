"""The tests for the Script component."""
# pylint: disable=protected-access
import unittest
from unittest.mock import patch

from homeassistant.components import script
from homeassistant.components.script import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_RELOAD, SERVICE_TOGGLE, SERVICE_TURN_OFF)
from homeassistant.core import Context, callback, split_entity_id
from homeassistant.loader import bind_hass
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant


ENTITY_ID = 'script.test'


@bind_hass
def turn_on(hass, entity_id, variables=None, context=None):
    """Turn script on.

    This is a legacy helper method. Do not use it for new tests.
    """
    _, object_id = split_entity_id(entity_id)

    hass.services.call(DOMAIN, object_id, variables, context=context)


@bind_hass
def turn_off(hass, entity_id):
    """Turn script on.

    This is a legacy helper method. Do not use it for new tests.
    """
    hass.services.call(DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id})


@bind_hass
def toggle(hass, entity_id):
    """Toggle the script.

    This is a legacy helper method. Do not use it for new tests.
    """
    hass.services.call(DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: entity_id})


@bind_hass
def reload(hass):
    """Reload script component.

    This is a legacy helper method. Do not use it for new tests.
    """
    hass.services.call(DOMAIN, SERVICE_RELOAD)


class TestScriptComponent(unittest.TestCase):
    """Test the Script component."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup_with_invalid_configs(self):
        """Test setup with invalid configs."""
        for value in (
            {'test': {}},
            {
                'test hello world': {
                    'sequence': [{'event': 'bla'}]
                }
            },
            {
                'test': {
                    'sequence': {
                        'event': 'test_event',
                        'service': 'homeassistant.turn_on',
                    }
                }
            },
        ):
            assert not setup_component(self.hass, 'script', {
                'script': value
            }), 'Script loaded with wrong config {}'.format(value)

            self.assertEqual(0, len(self.hass.states.entity_ids('script')))

    def test_turn_on_service(self):
        """Verify that the turn_on service."""
        event = 'test_event'
        events = []

        @callback
        def record_event(event):
            """Add recorded event to set."""
            events.append(event)

        self.hass.bus.listen(event, record_event)

        assert setup_component(self.hass, 'script', {
            'script': {
                'test': {
                    'sequence': [{
                        'delay': {
                            'seconds': 5
                        }
                    }, {
                        'event': event,
                    }]
                }
            }
        })

        turn_on(self.hass, ENTITY_ID)
        self.hass.block_till_done()
        self.assertTrue(script.is_on(self.hass, ENTITY_ID))
        self.assertEqual(0, len(events))

        # Calling turn_on a second time should not advance the script
        turn_on(self.hass, ENTITY_ID)
        self.hass.block_till_done()
        self.assertEqual(0, len(events))

        turn_off(self.hass, ENTITY_ID)
        self.hass.block_till_done()
        self.assertFalse(script.is_on(self.hass, ENTITY_ID))
        self.assertEqual(0, len(events))

        state = self.hass.states.get('group.all_scripts')
        assert state is not None
        assert state.attributes.get('entity_id') == (ENTITY_ID,)

    def test_toggle_service(self):
        """Test the toggling of a service."""
        event = 'test_event'
        events = []

        @callback
        def record_event(event):
            """Add recorded event to set."""
            events.append(event)

        self.hass.bus.listen(event, record_event)

        assert setup_component(self.hass, 'script', {
            'script': {
                'test': {
                    'sequence': [{
                        'delay': {
                            'seconds': 5
                        }
                    }, {
                        'event': event,
                    }]
                }
            }
        })

        toggle(self.hass, ENTITY_ID)
        self.hass.block_till_done()
        self.assertTrue(script.is_on(self.hass, ENTITY_ID))
        self.assertEqual(0, len(events))

        toggle(self.hass, ENTITY_ID)
        self.hass.block_till_done()
        self.assertFalse(script.is_on(self.hass, ENTITY_ID))
        self.assertEqual(0, len(events))

    def test_passing_variables(self):
        """Test different ways of passing in variables."""
        calls = []
        context = Context()

        @callback
        def record_call(service):
            """Add recorded event to set."""
            calls.append(service)

        self.hass.services.register('test', 'script', record_call)

        assert setup_component(self.hass, 'script', {
            'script': {
                'test': {
                    'sequence': {
                        'service': 'test.script',
                        'data_template': {
                            'hello': '{{ greeting }}',
                        },
                    },
                },
            },
        })

        turn_on(self.hass, ENTITY_ID, {
            'greeting': 'world'
        }, context=context)

        self.hass.block_till_done()

        assert len(calls) == 1
        assert calls[0].context is context
        assert calls[0].data['hello'] == 'world'

        self.hass.services.call('script', 'test', {
            'greeting': 'universe',
        }, context=context)

        self.hass.block_till_done()

        assert len(calls) == 2
        assert calls[1].context is context
        assert calls[1].data['hello'] == 'universe'

    def test_reload_service(self):
        """Verify that the turn_on service."""
        assert setup_component(self.hass, 'script', {
            'script': {
                'test': {
                    'sequence': [{
                        'delay': {
                            'seconds': 5
                        }
                    }]
                }
            }
        })

        assert self.hass.states.get(ENTITY_ID) is not None
        assert self.hass.services.has_service(script.DOMAIN, 'test')

        with patch('homeassistant.config.load_yaml_config_file', return_value={
                'script': {
                    'test2': {
                        'sequence': [{
                            'delay': {
                                'seconds': 5
                            }
                        }]
                    }}}):
            with patch('homeassistant.config.find_config_file',
                       return_value=''):
                reload(self.hass)
                self.hass.block_till_done()

        assert self.hass.states.get(ENTITY_ID) is None
        assert not self.hass.services.has_service(script.DOMAIN, 'test')

        assert self.hass.states.get("script.test2") is not None
        assert self.hass.services.has_service(script.DOMAIN, 'test2')
