"""The tests for the  Template switch platform."""
from homeassistant.core import callback
from homeassistant import setup
import homeassistant.components as core
from homeassistant.const import STATE_ON, STATE_OFF

from tests.common import (
    get_test_home_assistant, assert_setup_component)


class TestTemplateSwitch:
    """Test the Template switch."""

    hass = None
    calls = None
    # pylint: disable=invalid-name

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.calls = []

        @callback
        def record_call(service):
            """Track function calls.."""
            self.calls.append(service)

        self.hass.services.register('test', 'automation', record_call)

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_template_state_text(self):
        """"Test the state text of a template."""
        with assert_setup_component(1, 'switch'):
            assert setup.setup_component(self.hass, 'switch', {
                'switch': {
                    'platform': 'template',
                    'switches': {
                        'test_template_switch': {
                            'value_template':
                                "{{ states.switch.test_state.state }}",
                            'turn_on': {
                                'service': 'switch.turn_on',
                                'entity_id': 'switch.test_state'
                            },
                            'turn_off': {
                                'service': 'switch.turn_off',
                                'entity_id': 'switch.test_state'
                            },
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.set('switch.test_state', STATE_ON)
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test_template_switch')
        assert state.state == STATE_ON

        state = self.hass.states.set('switch.test_state', STATE_OFF)
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test_template_switch')
        assert state.state == STATE_OFF

    def test_template_state_boolean_on(self):
        """Test the setting of the state with boolean on."""
        with assert_setup_component(1, 'switch'):
            assert setup.setup_component(self.hass, 'switch', {
                'switch': {
                    'platform': 'template',
                    'switches': {
                        'test_template_switch': {
                            'value_template':
                                "{{ 1 == 1 }}",
                            'turn_on': {
                                'service': 'switch.turn_on',
                                'entity_id': 'switch.test_state'
                            },
                            'turn_off': {
                                'service': 'switch.turn_off',
                                'entity_id': 'switch.test_state'
                            },
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test_template_switch')
        assert state.state == STATE_ON

    def test_template_state_boolean_off(self):
        """Test the setting of the state with off."""
        with assert_setup_component(1, 'switch'):
            assert setup.setup_component(self.hass, 'switch', {
                'switch': {
                    'platform': 'template',
                    'switches': {
                        'test_template_switch': {
                            'value_template':
                                "{{ 1 == 2 }}",
                            'turn_on': {
                                'service': 'switch.turn_on',
                                'entity_id': 'switch.test_state'
                            },
                            'turn_off': {
                                'service': 'switch.turn_off',
                                'entity_id': 'switch.test_state'
                            },
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test_template_switch')
        assert state.state == STATE_OFF

    def test_icon_template(self):
        """Test icon template."""
        with assert_setup_component(1, 'switch'):
            assert setup.setup_component(self.hass, 'switch', {
                'switch': {
                    'platform': 'template',
                    'switches': {
                        'test_template_switch': {
                            'value_template':
                                "{{ states.switch.test_state.state }}",
                            'turn_on': {
                                'service': 'switch.turn_on',
                                'entity_id': 'switch.test_state'
                            },
                            'turn_off': {
                                'service': 'switch.turn_off',
                                'entity_id': 'switch.test_state'
                            },
                            'icon_template':
                                "{% if states.switch.test_state.state %}"
                                "mdi:check"
                                "{% endif %}"
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test_template_switch')
        assert state.attributes.get('icon') == ''

        state = self.hass.states.set('switch.test_state', STATE_ON)
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test_template_switch')
        assert state.attributes['icon'] == 'mdi:check'

    def test_template_syntax_error(self):
        """Test templating syntax error."""
        with assert_setup_component(0, 'switch'):
            assert setup.setup_component(self.hass, 'switch', {
                'switch': {
                    'platform': 'template',
                    'switches': {
                        'test_template_switch': {
                            'value_template':
                                "{% if rubbish %}",
                            'turn_on': {
                                'service': 'switch.turn_on',
                                'entity_id': 'switch.test_state'
                            },
                            'turn_off': {
                                'service': 'switch.turn_off',
                                'entity_id': 'switch.test_state'
                            },
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_invalid_name_does_not_create(self):
        """Test invalid name."""
        with assert_setup_component(0, 'switch'):
            assert setup.setup_component(self.hass, 'switch', {
                'switch': {
                    'platform': 'template',
                    'switches': {
                        'test INVALID switch': {
                            'value_template':
                                "{{ rubbish }",
                            'turn_on': {
                                'service': 'switch.turn_on',
                                'entity_id': 'switch.test_state'
                            },
                            'turn_off': {
                                'service': 'switch.turn_off',
                                'entity_id': 'switch.test_state'
                            },
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_invalid_switch_does_not_create(self):
        """Test invalid switch."""
        with assert_setup_component(0, 'switch'):
            assert setup.setup_component(self.hass, 'switch', {
                'switch': {
                    'platform': 'template',
                    'switches': {
                        'test_template_switch': 'Invalid'
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_no_switches_does_not_create(self):
        """Test if there are no switches no creation."""
        with assert_setup_component(0, 'switch'):
            assert setup.setup_component(self.hass, 'switch', {
                'switch': {
                    'platform': 'template'
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_missing_template_does_not_create(self):
        """Test missing template."""
        with assert_setup_component(0, 'switch'):
            assert setup.setup_component(self.hass, 'switch', {
                'switch': {
                    'platform': 'template',
                    'switches': {
                        'test_template_switch': {
                            'not_value_template':
                                "{{ states.switch.test_state.state }}",
                            'turn_on': {
                                'service': 'switch.turn_on',
                                'entity_id': 'switch.test_state'
                            },
                            'turn_off': {
                                'service': 'switch.turn_off',
                                'entity_id': 'switch.test_state'
                            },
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_missing_on_does_not_create(self):
        """Test missing on."""
        with assert_setup_component(0, 'switch'):
            assert setup.setup_component(self.hass, 'switch', {
                'switch': {
                    'platform': 'template',
                    'switches': {
                        'test_template_switch': {
                            'value_template':
                                "{{ states.switch.test_state.state }}",
                            'not_on': {
                                'service': 'switch.turn_on',
                                'entity_id': 'switch.test_state'
                            },
                            'turn_off': {
                                'service': 'switch.turn_off',
                                'entity_id': 'switch.test_state'
                            },
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_missing_off_does_not_create(self):
        """Test missing off."""
        with assert_setup_component(0, 'switch'):
            assert setup.setup_component(self.hass, 'switch', {
                'switch': {
                    'platform': 'template',
                    'switches': {
                        'test_template_switch': {
                            'value_template':
                                "{{ states.switch.test_state.state }}",
                            'turn_on': {
                                'service': 'switch.turn_on',
                                'entity_id': 'switch.test_state'
                            },
                            'not_off': {
                                'service': 'switch.turn_off',
                                'entity_id': 'switch.test_state'
                            },
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_on_action(self):
        """Test on action."""
        assert setup.setup_component(self.hass, 'switch', {
            'switch': {
                'platform': 'template',
                'switches': {
                    'test_template_switch': {
                        'value_template':
                            "{{ states.switch.test_state.state }}",
                        'turn_on': {
                            'service': 'test.automation'
                        },
                        'turn_off': {
                            'service': 'switch.turn_off',
                            'entity_id': 'switch.test_state'
                        },
                    }
                }
            }
        })

        self.hass.start()
        self.hass.block_till_done()

        self.hass.states.set('switch.test_state', STATE_OFF)
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test_template_switch')
        assert state.state == STATE_OFF

        core.switch.turn_on(self.hass, 'switch.test_template_switch')
        self.hass.block_till_done()

        assert len(self.calls) == 1

    def test_off_action(self):
        """Test off action."""
        assert setup.setup_component(self.hass, 'switch', {
            'switch': {
                'platform': 'template',
                'switches': {
                    'test_template_switch': {
                        'value_template':
                            "{{ states.switch.test_state.state }}",
                        'turn_on': {
                            'service': 'switch.turn_on',
                            'entity_id': 'switch.test_state'

                        },
                        'turn_off': {
                            'service': 'test.automation'
                        },
                    }
                }
            }
        })

        self.hass.start()
        self.hass.block_till_done()

        self.hass.states.set('switch.test_state', STATE_ON)
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test_template_switch')
        assert state.state == STATE_ON

        core.switch.turn_off(self.hass, 'switch.test_template_switch')
        self.hass.block_till_done()

        assert len(self.calls) == 1
