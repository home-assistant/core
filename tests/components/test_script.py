"""The tests for the Script component."""
# pylint: disable=too-many-public-methods,protected-access
from datetime import timedelta
import unittest

from homeassistant.components import script
import homeassistant.util.dt as dt_util

from tests.common import fire_time_changed, get_test_home_assistant


ENTITY_ID = 'script.test'


class TestScript(unittest.TestCase):
    """Test the Script component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup_with_missing_sequence(self):
        """Test setup with missing sequence."""
        self.assertTrue(script.setup(self.hass, {
            'script': {
                'test': {}
            }
        }))

        self.assertEqual(0, len(self.hass.states.entity_ids('script')))

    def test_setup_with_invalid_object_id(self):
        """Test setup with invalid objects."""
        self.assertTrue(script.setup(self.hass, {
            'script': {
                'test hello world': {
                    'sequence': []
                }
            }
        }))

        self.assertEqual(0, len(self.hass.states.entity_ids('script')))

    def test_setup_with_dict_as_sequence(self):
        """Test setup with dict as sequence."""
        self.assertTrue(script.setup(self.hass, {
            'script': {
                'test': {
                    'sequence': {
                        'event': 'test_event'
                    }
                }
            }
        }))

        self.assertEqual(0, len(self.hass.states.entity_ids('script')))

    def test_firing_event(self):
        """Test the firing of events."""
        event = 'test_event'
        calls = []

        def record_event(event):
            """Add recorded event to set."""
            calls.append(event)

        self.hass.bus.listen(event, record_event)

        self.assertTrue(script.setup(self.hass, {
            'script': {
                'test': {
                    'alias': 'Test Script',
                    'sequence': [{
                        'event': event,
                        'event_data': {
                            'hello': 'world'
                        }
                    }]
                }
            }
        }))

        script.turn_on(self.hass, ENTITY_ID)
        self.hass.pool.block_till_done()

        self.assertEqual(1, len(calls))
        self.assertEqual('world', calls[0].data.get('hello'))
        self.assertIsNone(
            self.hass.states.get(ENTITY_ID).attributes.get('can_cancel'))

    def test_calling_service_old(self):
        """Test the calling of an old service."""
        calls = []

        def record_call(service):
            """Add recorded event to set."""
            calls.append(service)

        self.hass.services.register('test', 'script', record_call)

        self.assertTrue(script.setup(self.hass, {
            'script': {
                'test': {
                    'sequence': [{
                        'execute_service': 'test.script',
                        'service_data': {
                            'hello': 'world'
                        }
                    }]
                }
            }
        }))

        script.turn_on(self.hass, ENTITY_ID)
        self.hass.pool.block_till_done()

        self.assertEqual(1, len(calls))
        self.assertEqual('world', calls[0].data.get('hello'))

    def test_calling_service(self):
        """Test the calling of a service."""
        calls = []

        def record_call(service):
            """Add recorded event to set."""
            calls.append(service)

        self.hass.services.register('test', 'script', record_call)

        self.assertTrue(script.setup(self.hass, {
            'script': {
                'test': {
                    'sequence': [{
                        'service': 'test.script',
                        'service_data': {
                            'hello': 'world'
                        }
                    }]
                }
            }
        }))

        script.turn_on(self.hass, ENTITY_ID)
        self.hass.pool.block_till_done()

        self.assertEqual(1, len(calls))
        self.assertEqual('world', calls[0].data.get('hello'))

    def test_delay(self):
        """Test the delay."""
        event = 'test_event'
        calls = []

        def record_event(event):
            """Add recorded event to set."""
            calls.append(event)

        self.hass.bus.listen(event, record_event)

        self.assertTrue(script.setup(self.hass, {
            'script': {
                'test': {
                    'sequence': [{
                        'event': event
                    }, {
                        'delay': {
                            'seconds': 5
                        }
                    }, {
                        'event': event,
                    }]
                }
            }
        }))

        script.turn_on(self.hass, ENTITY_ID)
        self.hass.pool.block_till_done()

        self.assertTrue(script.is_on(self.hass, ENTITY_ID))
        self.assertTrue(
            self.hass.states.get(ENTITY_ID).attributes.get('can_cancel'))

        self.assertEqual(
            event,
            self.hass.states.get(ENTITY_ID).attributes.get('last_action'))
        self.assertEqual(1, len(calls))

        future = dt_util.utcnow() + timedelta(seconds=5)
        fire_time_changed(self.hass, future)
        self.hass.pool.block_till_done()

        self.assertFalse(script.is_on(self.hass, ENTITY_ID))

        self.assertEqual(2, len(calls))

    def test_cancel_while_delay(self):
        """Test the cancelling while the delay is present."""
        event = 'test_event'
        calls = []

        def record_event(event):
            """Add recorded event to set."""
            calls.append(event)

        self.hass.bus.listen(event, record_event)

        self.assertTrue(script.setup(self.hass, {
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
        }))

        script.turn_on(self.hass, ENTITY_ID)
        self.hass.pool.block_till_done()

        self.assertTrue(script.is_on(self.hass, ENTITY_ID))

        self.assertEqual(0, len(calls))

        script.turn_off(self.hass, ENTITY_ID)
        self.hass.pool.block_till_done()
        self.assertFalse(script.is_on(self.hass, ENTITY_ID))

        future = dt_util.utcnow() + timedelta(seconds=5)
        fire_time_changed(self.hass, future)
        self.hass.pool.block_till_done()

        self.assertFalse(script.is_on(self.hass, ENTITY_ID))

        self.assertEqual(0, len(calls))

    def test_turn_on_service(self):
        """Verify that the turn_on service."""
        event = 'test_event'
        calls = []

        def record_event(event):
            """Add recorded event to set."""
            calls.append(event)

        self.hass.bus.listen(event, record_event)

        self.assertTrue(script.setup(self.hass, {
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
        }))

        script.turn_on(self.hass, ENTITY_ID)
        self.hass.pool.block_till_done()
        self.assertTrue(script.is_on(self.hass, ENTITY_ID))
        self.assertEqual(0, len(calls))

        # Calling turn_on a second time should not advance the script
        script.turn_on(self.hass, ENTITY_ID)
        self.hass.pool.block_till_done()
        self.assertEqual(0, len(calls))

    def test_toggle_service(self):
        """Test the toggling of a service."""
        event = 'test_event'
        calls = []

        def record_event(event):
            """Add recorded event to set."""
            calls.append(event)

        self.hass.bus.listen(event, record_event)

        self.assertTrue(script.setup(self.hass, {
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
        }))

        script.toggle(self.hass, ENTITY_ID)
        self.hass.pool.block_till_done()
        self.assertTrue(script.is_on(self.hass, ENTITY_ID))
        self.assertEqual(0, len(calls))

        script.toggle(self.hass, ENTITY_ID)
        self.hass.pool.block_till_done()
        self.assertFalse(script.is_on(self.hass, ENTITY_ID))
        self.assertEqual(0, len(calls))
