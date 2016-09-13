"""The test for state automation."""
import unittest
from datetime import timedelta
from unittest.mock import patch

from homeassistant.bootstrap import _setup_component
import homeassistant.util.dt as dt_util
import homeassistant.components.automation as automation

from tests.common import fire_time_changed, get_test_home_assistant


class TestAutomationState(unittest.TestCase):
    """Test the event automation."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.components.append('group')
        self.hass.states.set('test.entity', 'hello')
        self.calls = []

        def record_call(service):
            self.calls.append(service)

        self.hass.services.register('test', 'automation', record_call)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_if_fires_on_entity_change(self):
        """Test for firing on entity change."""
        self.hass.states.set('test.entity', 'hello')
        self.hass.block_till_done()

        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'state',
                    'entity_id': 'test.entity',
                },
                'action': {
                    'service': 'test.automation',
                    'data_template': {
                        'some': '{{ trigger.%s }}' % '}} - {{ trigger.'.join((
                                    'platform', 'entity_id',
                                    'from_state.state', 'to_state.state',
                                    'for'))
                    },
                }
            }
        })

        self.hass.states.set('test.entity', 'world')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual(
            'state - test.entity - hello - world - None',
            self.calls[0].data['some'])

        automation.turn_off(self.hass)
        self.hass.block_till_done()
        self.hass.states.set('test.entity', 'planet')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_entity_change_with_from_filter(self):
        """Test for firing on entity change with filter."""
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'state',
                    'entity_id': 'test.entity',
                    'from': 'hello'
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.states.set('test.entity', 'world')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_entity_change_with_to_filter(self):
        """Test for firing on entity change with no filter."""
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'state',
                    'entity_id': 'test.entity',
                    'to': 'world'
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.states.set('test.entity', 'world')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_entity_change_with_state_filter(self):
        """Test for firing on entity change with state filter."""
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'state',
                    'entity_id': 'test.entity',
                    'state': 'world'
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.states.set('test.entity', 'world')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_entity_change_with_both_filters(self):
        """Test for firing if both filters are a non match."""
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'state',
                    'entity_id': 'test.entity',
                    'from': 'hello',
                    'to': 'world'
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.states.set('test.entity', 'world')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_not_fires_if_to_filter_not_match(self):
        """Test for not firing if to filter is not a match."""
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'state',
                    'entity_id': 'test.entity',
                    'from': 'hello',
                    'to': 'world'
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.states.set('test.entity', 'moon')
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_not_fires_if_from_filter_not_match(self):
        """Test for not firing if from filter is not a match."""
        self.hass.states.set('test.entity', 'bye')

        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'state',
                    'entity_id': 'test.entity',
                    'from': 'hello',
                    'to': 'world'
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.states.set('test.entity', 'world')
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_not_fires_if_entity_not_match(self):
        """Test for not firing if entity is not matching."""
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'state',
                    'entity_id': 'test.anoter_entity',
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.states.set('test.entity', 'world')
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_action(self):
        """Test for to action."""
        entity_id = 'domain.test_entity'
        test_state = 'new_state'
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
                'condition': [{
                    'platform': 'state',
                    'entity_id': entity_id,
                    'state': test_state
                }],
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.states.set(entity_id, test_state)
        self.hass.bus.fire('test_event')
        self.hass.block_till_done()

        self.assertEqual(1, len(self.calls))

        self.hass.states.set(entity_id, test_state + 'something')
        self.hass.bus.fire('test_event')
        self.hass.block_till_done()

        self.assertEqual(1, len(self.calls))

    def test_if_fails_setup_if_to_boolean_value(self):
        """Test for setup failure for boolean to."""
        assert not _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'state',
                    'entity_id': 'test.entity',
                    'to': True,
                },
                'action': {
                    'service': 'homeassistant.turn_on',
                }
            }})

    def test_if_fails_setup_if_from_boolean_value(self):
        """Test for setup failure for boolean from."""
        assert not _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'state',
                    'entity_id': 'test.entity',
                    'from': True,
                },
                'action': {
                    'service': 'homeassistant.turn_on',
                }
            }})

    def test_if_fails_setup_bad_for(self):
        """Test for setup failure for bad for."""
        assert not _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'state',
                    'entity_id': 'test.entity',
                    'to': 'world',
                    'for': {
                        'invalid': 5
                    },
                },
                'action': {
                    'service': 'homeassistant.turn_on',
                }
            }})

    def test_if_fails_setup_for_without_to(self):
        """Test for setup failures for missing to."""
        assert not _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'state',
                    'entity_id': 'test.entity',
                    'for': {
                        'seconds': 5
                    },
                },
                'action': {
                    'service': 'homeassistant.turn_on',
                }
            }})

    def test_if_not_fires_on_entity_change_with_for(self):
        """Test for not firing on entity change with for."""
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'state',
                    'entity_id': 'test.entity',
                    'to': 'world',
                    'for': {
                        'seconds': 5
                    },
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.states.set('test.entity', 'world')
        self.hass.block_till_done()
        self.hass.states.set('test.entity', 'not_world')
        self.hass.block_till_done()
        fire_time_changed(self.hass, dt_util.utcnow() + timedelta(seconds=10))
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_fires_on_entity_change_with_for(self):
        """Test for firing on entity change with for."""
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'state',
                    'entity_id': 'test.entity',
                    'to': 'world',
                    'for': {
                        'seconds': 5
                    },
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.states.set('test.entity', 'world')
        self.hass.block_till_done()
        fire_time_changed(self.hass, dt_util.utcnow() + timedelta(seconds=10))
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_for_condition(self):
        """Test for firing if contition is on."""
        point1 = dt_util.utcnow()
        point2 = point1 + timedelta(seconds=10)
        with patch('homeassistant.core.dt_util.utcnow') as mock_utcnow:
            mock_utcnow.return_value = point1
            self.hass.states.set('test.entity', 'on')
            assert _setup_component(self.hass, automation.DOMAIN, {
                automation.DOMAIN: {
                    'trigger': {
                        'platform': 'event',
                        'event_type': 'test_event',
                    },
                    'condition': {
                        'platform': 'state',
                        'entity_id': 'test.entity',
                        'state': 'on',
                        'for': {
                            'seconds': 5
                        },
                    },
                    'action': {'service': 'test.automation'},
                }
            })

            # not enough time has passed
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
            self.assertEqual(0, len(self.calls))

            # Time travel 10 secs into the future
            mock_utcnow.return_value = point2
            self.hass.bus.fire('test_event')
            self.hass.block_till_done()
            self.assertEqual(1, len(self.calls))

    def test_if_fails_setup_for_without_time(self):
        """Test for setup failure if no time is provided."""
        assert not _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'bla'
                },
                'condition': {
                    'platform': 'state',
                    'entity_id': 'test.entity',
                    'state': 'on',
                    'for': {},
                },
                'action': {'service': 'test.automation'},
            }})

    def test_if_fails_setup_for_without_entity(self):
        """Test for setup failure if no entity is provided."""
        assert not _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {'event_type': 'bla'},
                'condition': {
                    'platform': 'state',
                    'state': 'on',
                    'for': {
                        'seconds': 5
                    },
                },
                'action': {'service': 'test.automation'},
            }})
