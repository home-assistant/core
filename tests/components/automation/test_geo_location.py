"""The tests for the geo location trigger."""
import unittest

from homeassistant.components import automation, zone
from homeassistant.core import callback, Context
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant, mock_component
from tests.components.automation import common


class TestAutomationGeoLocation(unittest.TestCase):
    """Test the geo location trigger."""

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
        self.hass.states.set('geo_location.entity', 'hello', {
            'latitude': 32.881011,
            'longitude': -117.234758,
            'source': 'test_source'
        })
        self.hass.block_till_done()

        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'geo_location',
                    'source': 'test_source',
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

        self.hass.states.set('geo_location.entity', 'hello', {
            'latitude': 32.880586,
            'longitude': -117.237564
        }, context=context)
        self.hass.block_till_done()

        self.assertEqual(1, len(self.calls))
        assert self.calls[0].context is context
        self.assertEqual(
            'geo_location - geo_location.entity - hello - hello - test',
            self.calls[0].data['some'])

        # Set out of zone again so we can trigger call
        self.hass.states.set('geo_location.entity', 'hello', {
            'latitude': 32.881011,
            'longitude': -117.234758
        })
        self.hass.block_till_done()

        common.turn_off(self.hass)
        self.hass.block_till_done()

        self.hass.states.set('geo_location.entity', 'hello', {
            'latitude': 32.880586,
            'longitude': -117.237564
        })
        self.hass.block_till_done()

        self.assertEqual(1, len(self.calls))

    def test_if_not_fires_for_enter_on_zone_leave(self):
        """Test for not firing on zone leave."""
        self.hass.states.set('geo_location.entity', 'hello', {
            'latitude': 32.880586,
            'longitude': -117.237564,
            'source': 'test_source'
        })
        self.hass.block_till_done()

        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'geo_location',
                    'source': 'test_source',
                    'zone': 'zone.test',
                    'event': 'enter',
                },
                'action': {
                    'service': 'test.automation',
                }
            }
        })

        self.hass.states.set('geo_location.entity', 'hello', {
            'latitude': 32.881011,
            'longitude': -117.234758
        })
        self.hass.block_till_done()

        self.assertEqual(0, len(self.calls))

    def test_if_fires_on_zone_leave(self):
        """Test for firing on zone leave."""
        self.hass.states.set('geo_location.entity', 'hello', {
            'latitude': 32.880586,
            'longitude': -117.237564,
            'source': 'test_source'
        })
        self.hass.block_till_done()

        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'geo_location',
                    'source': 'test_source',
                    'zone': 'zone.test',
                    'event': 'leave',
                },
                'action': {
                    'service': 'test.automation',
                }
            }
        })

        self.hass.states.set('geo_location.entity', 'hello', {
            'latitude': 32.881011,
            'longitude': -117.234758,
            'source': 'test_source'
        })
        self.hass.block_till_done()

        self.assertEqual(1, len(self.calls))

    def test_if_not_fires_for_leave_on_zone_enter(self):
        """Test for not firing on zone enter."""
        self.hass.states.set('geo_location.entity', 'hello', {
            'latitude': 32.881011,
            'longitude': -117.234758,
            'source': 'test_source'
        })
        self.hass.block_till_done()

        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'geo_location',
                    'source': 'test_source',
                    'zone': 'zone.test',
                    'event': 'leave',
                },
                'action': {
                    'service': 'test.automation',
                }
            }
        })

        self.hass.states.set('geo_location.entity', 'hello', {
            'latitude': 32.880586,
            'longitude': -117.237564
        })
        self.hass.block_till_done()

        self.assertEqual(0, len(self.calls))

    def test_if_fires_on_zone_appear(self):
        """Test for firing if entity appears in zone."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'geo_location',
                    'source': 'test_source',
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

        # Entity appears in zone without previously existing outside the zone.
        context = Context()
        self.hass.states.set('geo_location.entity', 'hello', {
            'latitude': 32.880586,
            'longitude': -117.237564,
            'source': 'test_source'
        }, context=context)
        self.hass.block_till_done()

        self.assertEqual(1, len(self.calls))
        assert self.calls[0].context is context
        self.assertEqual(
            'geo_location - geo_location.entity -  - hello - test',
            self.calls[0].data['some'])

    def test_if_fires_on_zone_disappear(self):
        """Test for firing if entity disappears from zone."""
        self.hass.states.set('geo_location.entity', 'hello', {
            'latitude': 32.880586,
            'longitude': -117.237564,
            'source': 'test_source'
        })
        self.hass.block_till_done()

        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'geo_location',
                    'source': 'test_source',
                    'zone': 'zone.test',
                    'event': 'leave',
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

        # Entity disappears from zone without new coordinates outside the zone.
        self.hass.states.async_remove('geo_location.entity')
        self.hass.block_till_done()

        self.assertEqual(1, len(self.calls))
        self.assertEqual(
            'geo_location - geo_location.entity - hello -  - test',
            self.calls[0].data['some'])
