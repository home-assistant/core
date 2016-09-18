"""The tests for the Template automation."""
import unittest

from homeassistant.bootstrap import _setup_component
import homeassistant.components.automation as automation

from tests.common import get_test_home_assistant


class TestAutomationTemplate(unittest.TestCase):
    """Test the event automation."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.components.append('group')
        self.hass.states.set('test.entity', 'hello')
        self.calls = []

        def record_call(service):
            """helper for recording calls."""
            self.calls.append(service)

        self.hass.services.register('test', 'automation', record_call)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_if_fires_on_change_bool(self):
        """Test for firing on boolean change."""
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'template',
                    'value_template': '{{ true }}',
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.states.set('test.entity', 'world')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

        automation.turn_off(self.hass)
        self.hass.block_till_done()

        self.hass.states.set('test.entity', 'planet')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_change_str(self):
        """Test for firing on change."""
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'template',
                    'value_template': 'true',
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.states.set('test.entity', 'world')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_change_str_crazy(self):
        """Test for firing on change."""
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'template',
                    'value_template': 'TrUE',
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.states.set('test.entity', 'world')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_not_fires_on_change_bool(self):
        """Test for not firing on boolean change."""
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'template',
                    'value_template': '{{ false }}',
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.states.set('test.entity', 'world')
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_not_fires_on_change_str(self):
        """Test for not firing on string change."""
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'template',
                    'value_template': 'False',
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.states.set('test.entity', 'world')
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_not_fires_on_change_str_crazy(self):
        """Test for not firing on string change."""
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'template',
                    'value_template': 'Anything other than "true" is false.',
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.states.set('test.entity', 'world')
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_fires_on_no_change(self):
        """Test for firing on no change."""
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'template',
                    'value_template': '{{ true }}',
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.block_till_done()
        self.calls = []

        self.hass.states.set('test.entity', 'hello')
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_fires_on_two_change(self):
        """Test for firing on two changes."""
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'template',
                    'value_template': '{{ true }}',
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        # Trigger once
        self.hass.states.set('test.entity', 'world')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

        # Trigger again
        self.hass.states.set('test.entity', 'world')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_change_with_template(self):
        """Test for firing on change with template."""
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'template',
                    'value_template': '{{ is_state("test.entity", "world") }}',
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.states.set('test.entity', 'world')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_not_fires_on_change_with_template(self):
        """Test for not firing on change with template."""
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'template',
                    'value_template': '{{ is_state("test.entity", "hello") }}',
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.block_till_done()
        self.calls = []

        self.hass.states.set('test.entity', 'world')
        self.hass.block_till_done()
        assert len(self.calls) == 0

    def test_if_fires_on_change_with_template_advanced(self):
        """Test for firing on change with template advanced."""
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'template',
                    'value_template': '''{%- if is_state("test.entity", "world") -%}
                                         true
                                         {%- else -%}
                                         false
                                         {%- endif -%}''',
                },
                'action': {
                    'service': 'test.automation',
                    'data_template': {
                        'some':
                        '{{ trigger.%s }}' % '}} - {{ trigger.'.join((
                            'platform', 'entity_id', 'from_state.state',
                            'to_state.state'))
                    },
                }
            }
        })

        self.hass.block_till_done()
        self.calls = []

        self.hass.states.set('test.entity', 'world')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))
        self.assertEqual(
            'template - test.entity - hello - world',
            self.calls[0].data['some'])

    def test_if_fires_on_no_change_with_template_advanced(self):
        """Test for firing on no change with template advanced."""
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'template',
                    'value_template': '''{%- if is_state("test.entity", "world") -%}
                                         true
                                         {%- else -%}
                                         false
                                         {%- endif -%}''',
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        # Different state
        self.hass.states.set('test.entity', 'worldz')
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

        # Different state
        self.hass.states.set('test.entity', 'hello')
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

    def test_if_fires_on_change_with_template_2(self):
        """Test for firing on change with template."""
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'template',
                    'value_template':
                    '{{ not is_state("test.entity", "world") }}',
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.block_till_done()
        self.calls = []

        self.hass.states.set('test.entity', 'world')
        self.hass.block_till_done()
        assert len(self.calls) == 0

        self.hass.states.set('test.entity', 'home')
        self.hass.block_till_done()
        assert len(self.calls) == 1

        self.hass.states.set('test.entity', 'work')
        self.hass.block_till_done()
        assert len(self.calls) == 1

        self.hass.states.set('test.entity', 'not_home')
        self.hass.block_till_done()
        assert len(self.calls) == 1

        self.hass.states.set('test.entity', 'world')
        self.hass.block_till_done()
        assert len(self.calls) == 1

        self.hass.states.set('test.entity', 'home')
        self.hass.block_till_done()
        assert len(self.calls) == 2

    def test_if_action(self):
        """Test for firing if action."""
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
                'condition': [{
                    'platform': 'template',
                    'value_template': '{{ is_state("test.entity", "world") }}'
                }],
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        # Condition is not true yet
        self.hass.bus.fire('test_event')
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

        # Change condition to true, but it shouldn't be triggered yet
        self.hass.states.set('test.entity', 'world')
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))

        # Condition is true and event is triggered
        self.hass.bus.fire('test_event')
        self.hass.block_till_done()
        self.assertEqual(1, len(self.calls))

    def test_if_fires_on_change_with_bad_template(self):
        """Test for firing on change with bad template."""
        assert not _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'template',
                    'value_template': '{{ ',
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

    def test_if_fires_on_change_with_bad_template_2(self):
        """Test for firing on change with bad template."""
        assert _setup_component(self.hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'template',
                    'value_template': '{{ xyz | round(0) }}',
                },
                'action': {
                    'service': 'test.automation'
                }
            }
        })

        self.hass.states.set('test.entity', 'world')
        self.hass.block_till_done()
        self.assertEqual(0, len(self.calls))
