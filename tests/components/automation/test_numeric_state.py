"""The tests for numeric state automation."""
import unittest

from homeassistant.bootstrap import _setup_component
import homeassistant.components.automation as automation

from tests.common import get_test_home_assistant


class TestAutomationNumericState(unittest.TestCase):
    """Test the event automation."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.components.append('group')
        self.calls = []

        def record_call(service):
            """Helper to record calls."""
            self.calls.append(service)

        self.hass.services.register('test', 'automation', record_call)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_if_fires_on_entity_change_below(self):
        """"Test the firing with changed entity."""
        assert _setup_component(self.hass, automation.DOMAIN, {
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
        """"Test the firing with changed entity."""
        self.hass.states.set('test.entity', 11)
        self.hass.block_till_done()

        assert _setup_component(self.hass, automation.DOMAIN, {
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

    def test_if_not_fires_on_entity_change_below_to_below(self):
        """"Test the firing with changed entity."""
        self.hass.states.set('test.entity', 9)
        self.hass.block_till_done()

        assert _setup_component(self.hass, automation.DOMAIN, {
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

        # 9 is below 10 so this should not fire again
        self.hass.states.set('test.entity', 8)
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_fires_on_entity_change_above(self):
        """"Test the firing with changed entity."""
        assert _setup_component(self.hass, automation.DOMAIN, {
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
        """"Test the firing with changed entity."""
        # set initial state
        self.hass.states.set('test.entity', 9)
        self.hass.block_till_done()

        assert _setup_component(self.hass, automation.DOMAIN, {
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
        """"Test the firing with changed entity."""
        # set initial state
        self.hass.states.set('test.entity', 11)
        self.hass.block_till_done()

        assert _setup_component(self.hass, automation.DOMAIN, {
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

        # 11 is above 10 so this should fire again
        self.hass.states.set('test.entity', 12)
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_fires_on_entity_change_below_range(self):
        """"Test the firing with changed entity."""
        assert _setup_component(self.hass, automation.DOMAIN, {
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
        """"Test the firing with changed entity."""
        assert _setup_component(self.hass, automation.DOMAIN, {
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
        """"Test the firing with changed entity."""
        self.hass.states.set('test.entity', 11)
        self.hass.block_till_done()

        assert _setup_component(self.hass, automation.DOMAIN, {
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
        """"Test the firing with changed entity."""
        self.hass.states.set('test.entity', 11)
        self.hass.block_till_done()

        assert _setup_component(self.hass, automation.DOMAIN, {
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
        """"Test if not fired with non matching entity."""
        assert _setup_component(self.hass, automation.DOMAIN, {
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
        """"Test attributes change."""
        assert _setup_component(self.hass, automation.DOMAIN, {
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
        """"Test attributes."""
        assert _setup_component(self.hass, automation.DOMAIN, {
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
        """"Test attributes change."""
        assert _setup_component(self.hass, automation.DOMAIN, {
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
        """"Test attributes change."""
        assert _setup_component(self.hass, automation.DOMAIN, {
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
        """"Test attributes change."""
        assert _setup_component(self.hass, automation.DOMAIN, {
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
        """"Test attributes change."""
        assert _setup_component(self.hass, automation.DOMAIN, {
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
        """"Test attributes change."""
        assert _setup_component(self.hass, automation.DOMAIN, {
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
        """"Test template list."""
        assert _setup_component(self.hass, automation.DOMAIN, {
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
        """"Test template string."""
        assert _setup_component(self.hass, automation.DOMAIN, {
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
        """"Test if not fired changed attributes."""
        assert _setup_component(self.hass, automation.DOMAIN, {
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
        """"Test if action."""
        entity_id = 'domain.test_entity'
        test_state = 10
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
                'condition': {
                    'platform': 'numeric_state',
                    'entity_id': entity_id,
                    'above': test_state,
                    'below': test_state + 2
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.states.set(entity_id, test_state)
        self.hass.bus.fire('test_event')
        self.hass.block_till_done()

        self.assertEqual(1, len(self.calls))

        self.hass.states.set(entity_id, test_state - 1)
        self.hass.bus.fire('test_event')
        self.hass.block_till_done()

        self.assertEqual(1, len(self.calls))

        self.hass.states.set(entity_id, test_state + 1)
        self.hass.bus.fire('test_event')
        self.hass.block_till_done()

        self.assertEqual(2, len(self.calls))
