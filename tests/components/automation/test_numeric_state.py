"""The tests for numeric state automation."""
from datetime import timedelta
import unittest
from unittest.mock import patch

import homeassistant.components.automation as automation
from homeassistant.core import callback
from homeassistant.setup import setup_component
import homeassistant.util.dt as dt_util

from tests.common import (
    get_test_home_assistant, mock_component, fire_time_changed,
    assert_setup_component)


# pylint: disable=invalid-name
class TestAutomationNumericState(unittest.TestCase):
    """Test the event automation."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_component(self.hass, 'group')
        self.calls = []

        @callback
        def record_call(service):
            """Helper to record calls."""
            self.calls.append(service)

        self.hass.services.register('test', 'automation', record_call)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_if_fires_on_entity_change_below(self):
        """Test the firing with changed entity."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'below': 10,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })
        # 9 is below 10
        self.hass.states.set('test.entity', 9)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

        # Set above 12 so the automation will fire again
        self.hass.states.set('test.entity', 12)
        automation.turn_off(self.hass)
        self.hass.block_till_done()
        self.hass.states.set('test.entity', 9)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_entity_change_over_to_below(self):
        """Test the firing with changed entity."""
        self.hass.states.set('test.entity', 11)
        self.hass.block_till_done()

        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'below': 10,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        # 9 is below 10
        self.hass.states.set('test.entity', 9)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_entities_change_over_to_below(self):
        """Test the firing with changed entities."""
        self.hass.states.set('test.entity_1', 11)
        self.hass.states.set('test.entity_2', 11)
        self.hass.block_till_done()

        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': [
                        'test.entity_1',
                        'test.entity_2',
                    ],
                    'below': 10,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        # 9 is below 10
        self.hass.states.set('test.entity_1', 9)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.hass.states.set('test.entity_2', 9)
        self.hass.block_till_done()
        self.assertEqual(2, len(self.calls))

    def test_if_not_fires_on_entity_change_below_to_below(self):
        """Test the firing with changed entity."""
        self.hass.states.set('test.entity', 11)
        self.hass.block_till_done()

        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'below': 10,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        # 9 is below 10 so this should fire
        self.hass.states.set('test.entity', 9)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

        # already below so should not fire again
        self.hass.states.set('test.entity', 5)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

        # still below so should not fire again
        self.hass.states.set('test.entity', 3)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_not_below_fires_on_entity_change_to_equal(self):
        """Test the firing with changed entity."""
        self.hass.states.set('test.entity', 11)
        self.hass.block_till_done()

        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'below': 10,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        # 10 is not below 10 so this should not fire again
        self.hass.states.set('test.entity', 10)
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_fires_on_initial_entity_below(self):
        """Test the firing when starting with a match."""
        self.hass.states.set('test.entity', 9)
        self.hass.block_till_done()

        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'below': 10,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        # Fire on first update even if initial state was already below
        self.hass.states.set('test.entity', 8)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_initial_entity_above(self):
        """Test the firing when starting with a match."""
        self.hass.states.set('test.entity', 11)
        self.hass.block_till_done()

        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'above': 10,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        # Fire on first update even if initial state was already above
        self.hass.states.set('test.entity', 12)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_entity_change_above(self):
        """Test the firing with changed entity."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'above': 10,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })
        # 11 is above 10
        self.hass.states.set('test.entity', 11)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_entity_change_below_to_above(self):
        """Test the firing with changed entity."""
        # set initial state
        self.hass.states.set('test.entity', 9)
        self.hass.block_till_done()

        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'above': 10,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        # 11 is above 10 and 9 is below
        self.hass.states.set('test.entity', 11)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_not_fires_on_entity_change_above_to_above(self):
        """Test the firing with changed entity."""
        # set initial state
        self.hass.states.set('test.entity', 9)
        self.hass.block_till_done()

        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'above': 10,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        # 12 is above 10 so this should fire
        self.hass.states.set('test.entity', 12)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

        # already above, should not fire again
        self.hass.states.set('test.entity', 15)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_not_above_fires_on_entity_change_to_equal(self):
        """Test the firing with changed entity."""
        # set initial state
        self.hass.states.set('test.entity', 9)
        self.hass.block_till_done()

        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'above': 10,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        # 10 is not above 10 so this should not fire again
        self.hass.states.set('test.entity', 10)
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_fires_on_entity_change_below_range(self):
        """Test the firing with changed entity."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'below': 10,
                    'above': 5,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })
        # 9 is below 10
        self.hass.states.set('test.entity', 9)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_entity_change_below_above_range(self):
        """Test the firing with changed entity."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'below': 10,
                    'above': 5,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })
        # 4 is below 5
        self.hass.states.set('test.entity', 4)
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_fires_on_entity_change_over_to_below_range(self):
        """Test the firing with changed entity."""
        self.hass.states.set('test.entity', 11)
        self.hass.block_till_done()

        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'below': 10,
                    'above': 5,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        # 9 is below 10
        self.hass.states.set('test.entity', 9)
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_entity_change_over_to_below_above_range(self):
        """Test the firing with changed entity."""
        self.hass.states.set('test.entity', 11)
        self.hass.block_till_done()

        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'below': 10,
                    'above': 5,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        # 4 is below 5 so it should not fire
        self.hass.states.set('test.entity', 4)
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_not_fires_if_entity_not_match(self):
        """Test if not fired with non matching entity."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.another_entity',
                    'below': 100,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.states.set('test.entity', 11)
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_fires_on_entity_change_below_with_attribute(self):
        """Test attributes change."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'below': 10,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })
        # 9 is below 10
        self.hass.states.set('test.entity', 9, {'test_attribute': 11})
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_not_fires_on_entity_change_not_below_with_attribute(self):
        """Test attributes."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'below': 10,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })
        # 11 is not below 10
        self.hass.states.set('test.entity', 11, {'test_attribute': 9})
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_fires_on_attribute_change_with_attribute_below(self):
        """Test attributes change."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'value_template': '{{ state.attributes.test_attribute }}',
                    'below': 10,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })
        # 9 is below 10
        self.hass.states.set('test.entity', 'entity', {'test_attribute': 9})
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_not_fires_on_attribute_change_with_attribute_not_below(self):
        """Test attributes change."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'value_template': '{{ state.attributes.test_attribute }}',
                    'below': 10,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })
        # 11 is not below 10
        self.hass.states.set('test.entity', 'entity', {'test_attribute': 11})
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_not_fires_on_entity_change_with_attribute_below(self):
        """Test attributes change."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'value_template': '{{ state.attributes.test_attribute }}',
                    'below': 10,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })
        # 11 is not below 10, entity state value should not be tested
        self.hass.states.set('test.entity', '9', {'test_attribute': 11})
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_not_fires_on_entity_change_with_not_attribute_below(self):
        """Test attributes change."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'value_template': '{{ state.attributes.test_attribute }}',
                    'below': 10,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })
        # 11 is not below 10, entity state value should not be tested
        self.hass.states.set('test.entity', 'entity')
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_fires_on_attr_change_with_attribute_below_and_multiple_attr(self):
        """Test attributes change."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'value_template': '{{ state.attributes.test_attribute }}',
                    'below': 10,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })
        # 9 is not below 10
        self.hass.states.set('test.entity', 'entity',
                             {'test_attribute': 9, 'not_test_attribute': 11})
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_template_list(self):
        """Test template list."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'value_template':
                    '{{ state.attributes.test_attribute[2] }}',
                    'below': 10,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })
        # 3 is below 10
        self.hass.states.set('test.entity', 'entity',
                             {'test_attribute': [11, 15, 3]})
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_template_string(self):
        """Test template string."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'value_template':
                    '{{ state.attributes.test_attribute | multiply(10) }}',
                    'below': 10,
                },
                'action': {
                    'service': 'test.automation',
                    'data_template': {
                        'some': '{{ trigger.%s }}' % '}} - {{ trigger.'.join((
                            'platform', 'entity_id', 'below', 'above',
                            'from_state.state', 'to_state.state'))
                    },
                }
            }
        })
        self.hass.states.set('test.entity', 'test state 1',
                             {'test_attribute': '1.2'})
        self.hass.block_till_done()
        self.hass.states.set('test.entity', 'test state 2',
                             {'test_attribute': '0.9'})
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual(
            'numeric_state - test.entity - 10.0 - None - test state 1 - '
            'test state 2',
            self.calls[0].data['some'])

    def test_not_fires_on_attr_change_with_attr_not_below_multiple_attr(self):
        """Test if not fired changed attributes."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'value_template': '{{ state.attributes.test_attribute }}',
                    'below': 10,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })
        # 11 is not below 10
        self.hass.states.set('test.entity', 'entity',
                             {'test_attribute': 11, 'not_test_attribute': 9})
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_action(self):
        """Test if action."""
        entity_id = 'domain.test_entity'
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
                'condition': {
                    'condition': 'numeric_state',
                    'entity_id': entity_id,
                    'above': 8,
                    'below': 12,
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.states.set(entity_id, 10)
        self.hass.bus.fire('test_event')
        self.hass.block_till_done()

        self.assertEqual(1, len(self.calls))

        self.hass.states.set(entity_id, 8)
        self.hass.bus.fire('test_event')
        self.hass.block_till_done()

        self.assertEqual(1, len(self.calls))

        self.hass.states.set(entity_id, 9)
        self.hass.bus.fire('test_event')
        self.hass.block_till_done()

        self.assertEqual(2, len(self.calls))

    def test_if_fails_setup_bad_for(self):
        """Test for setup failure for bad for."""
        with assert_setup_component(0):
            assert setup_component(self.hass, automation.DOMAIN, {
                automation.DOMAIN: {
                    'trigger': {
                        'platform': 'numeric_state',
                        'entity_id': 'test.entity',
                        'above': 8,
                        'below': 12,
                        'for': {
                            'invalid': 5
                        },
                    },
                    'action': {
                        'service': 'homeassistant.turn_on',
                    }
                }})

    def test_if_fails_setup_for_without_above_below(self):
        """Test for setup failures for missing above or below."""
        with assert_setup_component(0):
            assert setup_component(self.hass, automation.DOMAIN, {
                automation.DOMAIN: {
                    'trigger': {
                        'platform': 'numeric_state',
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
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'above': 8,
                    'below': 12,
                    'for': {
                        'seconds': 5
                    },
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.states.set('test.entity', 9)
        self.hass.block_till_done()
        self.hass.states.set('test.entity', 15)
        self.hass.block_till_done()
        fire_time_changed(self.hass, dt_util.utcnow() + timedelta(seconds=10))
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_not_fires_on_entities_change_with_for_after_stop(self):
        """Test for not firing on entities change with for after stop."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': [
                        'test.entity_1',
                        'test.entity_2',
                    ],
                    'above': 8,
                    'below': 12,
                    'for': {
                        'seconds': 5
                    },
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.states.set('test.entity_1', 9)
        self.hass.states.set('test.entity_2', 9)
        self.hass.block_till_done()
        fire_time_changed(self.hass, dt_util.utcnow() + timedelta(seconds=10))
        self.hass.block_till_done()
        self.assertEqual(2, len(self.calls))

        self.hass.states.set('test.entity_1', 15)
        self.hass.states.set('test.entity_2', 15)
        self.hass.block_till_done()
        self.hass.states.set('test.entity_1', 9)
        self.hass.states.set('test.entity_2', 9)
        self.hass.block_till_done()
        automation.turn_off(self.hass)
        self.hass.block_till_done()

        fire_time_changed(self.hass, dt_util.utcnow() + timedelta(seconds=10))
        self.hass.block_till_done()
        self.assertEqual(2, len(self.calls))

    def test_if_fires_on_entity_change_with_for_attribute_change(self):
        """Test for firing on entity change with for and attribute change."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'above': 8,
                    'below': 12,
                    'for': {
                        'seconds': 5
                    },
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        utcnow = dt_util.utcnow()
        with patch('homeassistant.core.dt_util.utcnow') as mock_utcnow:
            mock_utcnow.return_value = utcnow
            self.hass.states.set('test.entity', 9)
            self.hass.block_till_done()
            mock_utcnow.return_value += timedelta(seconds=4)
            fire_time_changed(self.hass, mock_utcnow.return_value)
            self.hass.states.set('test.entity', 9,
                                 attributes={"mock_attr": "attr_change"})
            self.hass.block_till_done()
            self.assertEqual(0, len(self.calls))
            mock_utcnow.return_value += timedelta(seconds=4)
            fire_time_changed(self.hass, mock_utcnow.return_value)
            self.hass.block_till_done()
            self.assertEqual(1, len(self.calls))

    def test_if_fires_on_entity_change_with_for(self):
        """Test for firing on entity change with for."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'above': 8,
                    'below': 12,
                    'for': {
                        'seconds': 5
                    },
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.states.set('test.entity', 9)
        self.hass.block_till_done()
        fire_time_changed(self.hass, dt_util.utcnow() + timedelta(seconds=10))
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_wait_template_with_trigger(self):
        """Test using wait template with 'trigger.entity_id'."""
        assert setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'numeric_state',
                    'entity_id': 'test.entity',
                    'above': 10,
                },
                'action': [
                    {'wait_template':
                        "{{ states(trigger.entity_id) | int < 10 }}"},
                    {'service': 'test.automation',
                     'data_template': {
                        'some':
                        '{{ trigger.%s }}' % '}} - {{ trigger.'.join((
                            'platform', 'entity_id', 'to_state.state'))
                        }}
                ],
            }
        })

        self.hass.block_till_done()
        self.calls = []

        self.hass.states.set('test.entity', '12')
        self.hass.block_till_done()
        self.hass.states.set('test.entity', '8')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual(
            'numeric_state - test.entity - 12',
            self.calls[0].data['some'])
