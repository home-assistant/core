"""The tests for the location automation."""
import unittest

from homeassistant.core import Context, callback
from homeassistant.setup import setup_component
from homeassistant.components import automation, zone

from tests.common import get_test_home_assistant, mock_component
from tests.components.automation import common


# pylint: disable=invalid-name
class TestAutomationZone(unittest.TestCase):
    """Test the event automation."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_component(self.hass, 'group')
        assert setup_component(self.hass, zone.DOMAIN, {
            'zone': {
                'name': 'test',
                'latitude': 32.880837,
                'longitude': -117.237561,
                'radius': 250,
            }
        })

        self.calls = []

        @callback
        def record_call(service):
            """Record calls."""
            self.calls.append(service)

        self.hass.services.register('test', 'automation', record_call)

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_if_fires_on_zone_enter(self):
        """Test for firing on zone enter."""
        context = Context()
        self.hass.states.set('test.entity', 'hello', {
            'latitude': 32.881011,
            'longitude': -117.234758
        })
        self.hass.block_till_done()

        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'zone',
                    'entity_id': 'test.entity',
                    'zone': 'zone.test',
                    'event': 'enter',
                },
                'action': {
                    'service': 'test.automation',
                    'data_template': {
                        'some': '{{ trigger.%s }}' % '}} - {{ trigger.'.join((
                            'platform', 'entity_id',
                            'from_state.state', 'to_state.state',
                            'zone.name'))
                    },

                }
            }
        })

        self.hass.states.set('test.entity', 'hello', {
            'latitude': 32.880586,
            'longitude': -117.237564
        }, context=context)
        self.hass.block_till_done()

        self.assertEqual(1, len(self.calls))
        assert self.calls[0].context is context
        self.assertEqual(
            'zone - test.entity - hello - hello - test',
            self.calls[0].data['some'])

        # Set out of zone again so we can trigger call
        self.hass.states.set('test.entity', 'hello', {
            'latitude': 32.881011,
            'longitude': -117.234758
        })
        self.hass.block_till_done()

        common.turn_off(self.hass)
        self.hass.block_till_done()

        self.hass.states.set('test.entity', 'hello', {
            'latitude': 32.880586,
            'longitude': -117.237564
        })
        self.hass.block_till_done()

        self.assertEqual(1, len(self.calls))

    def test_if_not_fires_for_enter_on_zone_leave(self):
        """Test for not firing on zone leave."""
        self.hass.states.set('test.entity', 'hello', {
            'latitude': 32.880586,
            'longitude': -117.237564
        })
        self.hass.block_till_done()

        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'zone',
                    'entity_id': 'test.entity',
                    'zone': 'zone.test',
                    'event': 'enter',
                },
                'action': {
                    'service': 'test.automation',
                }
            }
        })

        self.hass.states.set('test.entity', 'hello', {
            'latitude': 32.881011,
            'longitude': -117.234758
        })
        self.hass.block_till_done()

        self.assertEqual(0, len(self.calls))

    def test_if_fires_on_zone_leave(self):
        """Test for firing on zone leave."""
        self.hass.states.set('test.entity', 'hello', {
            'latitude': 32.880586,
            'longitude': -117.237564
        })
        self.hass.block_till_done()

        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'zone',
                    'entity_id': 'test.entity',
                    'zone': 'zone.test',
                    'event': 'leave',
                },
                'action': {
                    'service': 'test.automation',
                }
            }
        })

        self.hass.states.set('test.entity', 'hello', {
            'latitude': 32.881011,
            'longitude': -117.234758
        })
        self.hass.block_till_done()

        self.assertEqual(1, len(self.calls))

    def test_if_not_fires_for_leave_on_zone_enter(self):
        """Test for not firing on zone enter."""
        self.hass.states.set('test.entity', 'hello', {
            'latitude': 32.881011,
            'longitude': -117.234758
        })
        self.hass.block_till_done()

        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'zone',
                    'entity_id': 'test.entity',
                    'zone': 'zone.test',
                    'event': 'leave',
                },
                'action': {
                    'service': 'test.automation',
                }
            }
        })

        self.hass.states.set('test.entity', 'hello', {
            'latitude': 32.880586,
            'longitude': -117.237564
        })
        self.hass.block_till_done()

        self.assertEqual(0, len(self.calls))

    def test_zone_condition(self):
        """Test for zone condition."""
        self.hass.states.set('test.entity', 'hello', {
            'latitude': 32.880586,
            'longitude': -117.237564
        })
        self.hass.block_till_done()

        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event'
                },
                'condition': {
                    'condition': 'zone',
                    'entity_id': 'test.entity',
                    'zone': 'zone.test',
                },
                'action': {
                    'service': 'test.automation',
                }
            }
        })

        self.hass.bus.fire('test_event')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
