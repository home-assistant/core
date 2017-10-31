"""The tests for the Event automation."""
import unittest

from homeassistant.core import callback
from homeassistant.setup import setup_component
import homeassistant.components.automation as automation

from tests.common import get_test_home_assistant, mock_component


# pylint: disable=invalid-name
class TestAutomationEvent(unittest.TestCase):
    """Test the event automation."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_component(self.hass, 'group')
        self.calls = []

        @callback
        def record_call(service):
            """Helper for recording the call."""
            self.calls.append(service)

        self.hass.services.register('test', 'automation', record_call)

    def tearDown(self):
        """"Stop everything that was started."""
        self.hass.stop()

    def test_if_fires_on_event(self):
        """Test the firing of events."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
                'action': {
                    'service': 'test.automation',
                }
            }
        })

        self.hass.bus.fire('test_event')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

        automation.turn_off(self.hass)
        self.hass.block_till_done()

        self.hass.bus.fire('test_event')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_event_extra_data(self):
        """Test the firing of events still matches with event data."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
                'action': {
                    'service': 'test.automation',
                }
            }
        })

        self.hass.bus.fire('test_event', {'extra_key': 'extra_data'})
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

        automation.turn_off(self.hass)
        self.hass.block_till_done()

        self.hass.bus.fire('test_event')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_event_with_data(self):
        """Test the firing of events with data."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                    'event_data': {'some_attr': 'some_value'}
                },
                'action': {
                    'service': 'test.automation',
                }
            }
        })

        self.hass.bus.fire('test_event', {'some_attr': 'some_value',
                                          'another': 'value'})
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_event_with_empty_data_config(self):
        """Test the firing of events with empty data config.

        The frontend automation editor can produce configurations with an
        empty dict for event_data instead of no key.
        """
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                    'event_data': {}
                },
                'action': {
                    'service': 'test.automation',
                }
            }
        })

        self.hass.bus.fire('test_event', {'some_attr': 'some_value',
                                          'another': 'value'})
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_event_with_nested_data(self):
        """Test the firing of events with nested data."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                    'event_data': {
                        'parent_attr': {
                            'some_attr': 'some_value'
                        }
                    }
                },
                'action': {
                    'service': 'test.automation',
                }
            }
        })

        self.hass.bus.fire('test_event', {
            'parent_attr': {
                'some_attr': 'some_value',
                'another': 'value'
            }
        })
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_not_fires_if_event_data_not_matches(self):
        """Test firing of event if no match."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                    'event_data': {'some_attr': 'some_value'}
                },
                'action': {
                    'service': 'test.automation',
                }
            }
        })

        self.hass.bus.fire('test_event', {'some_attr': 'some_other_value'})
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))
