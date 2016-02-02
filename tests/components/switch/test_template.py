"""
tests.components.switch.template
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests template switch.
"""

import homeassistant.core as ha
import homeassistant.components.switch as switch


class TestTemplateSwitch:
    """ Test the Template switch. """

    def setup_method(self, method):
        self.hass = ha.HomeAssistant()

    def teardown_method(self, method):
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_template_state(self):
        assert switch.setup(self.hass, {
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


        state = self.hass.states.set('switch.test_state', 'On')
        self.hass.pool.block_till_done()

        state = self.hass.states.get('switch.test_template_switch')
        assert state.state == 'On'

        state = self.hass.states.set('switch.test_state', 'Off')
        self.hass.pool.block_till_done()

        state = self.hass.states.get('switch.test_template_switch')
        assert state.state == 'Off'


    def test_template_syntax_error(self):
        assert switch.setup(self.hass, {
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

        state = self.hass.states.set('switch.test_state', 'On')
        self.hass.pool.block_till_done()
        state = self.hass.states.get('switch.test_template_switch')
        assert state.state == 'error'

    def test_invalid_name_does_not_create(self):
        assert switch.setup(self.hass, {
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
        assert self.hass.states.all() == []

    def test_invalid_switch_does_not_create(self):
        assert switch.setup(self.hass, {
            'switch': {
                'platform': 'template',
                'switches': {
                    'test_template_switch': 'Invalid'
                }
            }
        })
        assert self.hass.states.all() == []

    def test_no_switches_does_not_create(self):
        assert switch.setup(self.hass, {
            'switch': {
                'platform': 'template'
            }
        })
        assert self.hass.states.all() == []

    def test_missing_template_does_not_create(self):
        assert switch.setup(self.hass, {
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
        assert self.hass.states.all() == []

    def test_missing_on_does_not_create(self):
        assert switch.setup(self.hass, {
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
        assert self.hass.states.all() == []

    def test_missing_off_does_not_create(self):
        assert switch.setup(self.hass, {
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
        assert self.hass.states.all() == []
