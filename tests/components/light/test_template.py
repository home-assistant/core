"""The tests for the  Template light platform."""
import logging

from homeassistant.core import callback
from homeassistant import setup
import homeassistant.components as core
from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.const import STATE_ON, STATE_OFF

from tests.common import (
    get_test_home_assistant, assert_setup_component)
_LOGGER = logging.getLogger(__name__)


class TestTemplateLight:
    """Test the Template light."""

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
        """Test the state text of a template."""
        with assert_setup_component(1, 'light'):
            assert setup.setup_component(self.hass, 'light', {
                'light': {
                    'platform': 'template',
                    'lights': {
                        'test_template_light': {
                            'value_template':
                                "{{ states.light.test_state.state }}",
                            'turn_on': {
                                'service': 'light.turn_on',
                                'entity_id': 'light.test_state'
                            },
                            'turn_off': {
                                'service': 'light.turn_off',
                                'entity_id': 'light.test_state'
                            },
                            'set_level': {
                                'service': 'light.turn_on',
                                'data_template': {
                                    'entity_id': 'light.test_state',
                                    'brightness': '{{brightness}}'
                                }
                            }
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.set('light.test_state', STATE_ON)
        self.hass.block_till_done()

        state = self.hass.states.get('light.test_template_light')
        assert state.state == STATE_ON

        state = self.hass.states.set('light.test_state', STATE_OFF)
        self.hass.block_till_done()

        state = self.hass.states.get('light.test_template_light')
        assert state.state == STATE_OFF

    def test_template_state_boolean_on(self):
        """Test the setting of the state with boolean on."""
        with assert_setup_component(1, 'light'):
            assert setup.setup_component(self.hass, 'light', {
                'light': {
                    'platform': 'template',
                    'lights': {
                        'test_template_light': {
                            'value_template': "{{ 1 == 1 }}",
                            'turn_on': {
                                'service': 'light.turn_on',
                                'entity_id': 'light.test_state'
                            },
                            'turn_off': {
                                'service': 'light.turn_off',
                                'entity_id': 'light.test_state'
                            },
                            'set_level': {
                                'service': 'light.turn_on',
                                'data_template': {
                                    'entity_id': 'light.test_state',
                                    'brightness': '{{brightness}}'
                                }
                            }
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('light.test_template_light')
        assert state.state == STATE_ON

    def test_template_state_boolean_off(self):
        """Test the setting of the state with off."""
        with assert_setup_component(1, 'light'):
            assert setup.setup_component(self.hass, 'light', {
                'light': {
                    'platform': 'template',
                    'lights': {
                        'test_template_light': {
                            'value_template': "{{ 1 == 2 }}",
                            'turn_on': {
                                'service': 'light.turn_on',
                                'entity_id': 'light.test_state'
                            },
                            'turn_off': {
                                'service': 'light.turn_off',
                                'entity_id': 'light.test_state'
                            },
                            'set_level': {
                                'service': 'light.turn_on',
                                'data_template': {
                                    'entity_id': 'light.test_state',
                                    'brightness': '{{brightness}}'
                                }
                            }
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('light.test_template_light')
        assert state.state == STATE_OFF

    def test_template_syntax_error(self):
        """Test templating syntax error."""
        with assert_setup_component(0, 'light'):
            assert setup.setup_component(self.hass, 'light', {
                'light': {
                    'platform': 'template',
                    'lights': {
                        'test_template_light': {
                            'value_template': "{%- if false -%}",
                            'turn_on': {
                                'service': 'light.turn_on',
                                'entity_id': 'light.test_state'
                            },
                            'turn_off': {
                                'service': 'light.turn_off',
                                'entity_id': 'light.test_state'
                            },
                            'set_level': {
                                'service': 'light.turn_on',
                                'data_template': {
                                    'entity_id': 'light.test_state',
                                    'brightness': '{{brightness}}'
                                }
                            }
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_invalid_name_does_not_create(self):
        """Test invalid name."""
        with assert_setup_component(0, 'light'):
            assert setup.setup_component(self.hass, 'light', {
                'light': {
                    'platform': 'template',
                    'lights': {
                        'bad name here': {
                            'value_template': "{{ 1== 1}}",
                            'turn_on': {
                                'service': 'light.turn_on',
                                'entity_id': 'light.test_state'
                            },
                            'turn_off': {
                                'service': 'light.turn_off',
                                'entity_id': 'light.test_state'
                            },
                            'set_level': {
                                'service': 'light.turn_on',
                                'data_template': {
                                    'entity_id': 'light.test_state',
                                    'brightness': '{{brightness}}'
                                }
                            }
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_invalid_light_does_not_create(self):
        """Test invalid light."""
        with assert_setup_component(0, 'light'):
            assert setup.setup_component(self.hass, 'light', {
                'light': {
                    'platform': 'template',
                    'switches': {
                        'test_template_light': 'Invalid'
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_no_lights_does_not_create(self):
        """Test if there are no lights no creation."""
        with assert_setup_component(0, 'light'):
            assert setup.setup_component(self.hass, 'light', {
                'light': {
                    'platform': 'template'
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_missing_template_does_create(self):
        """Test missing template."""
        with assert_setup_component(1, 'light'):
            assert setup.setup_component(self.hass, 'light', {
                'light': {
                    'platform': 'template',
                    'lights': {
                        'light_one': {
                            'turn_on': {
                                'service': 'light.turn_on',
                                'entity_id': 'light.test_state'
                            },
                            'turn_off': {
                                'service': 'light.turn_off',
                                'entity_id': 'light.test_state'
                            },
                            'set_level': {
                                'service': 'light.turn_on',
                                'data_template': {
                                    'entity_id': 'light.test_state',
                                    'brightness': '{{brightness}}'
                                }
                            }
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() != []

    def test_missing_on_does_not_create(self):
        """Test missing on."""
        with assert_setup_component(0, 'light'):
            assert setup.setup_component(self.hass, 'light', {
                'light': {
                    'platform': 'template',
                    'lights': {
                        'bad name here': {
                            'value_template': "{{ 1== 1}}",
                            'turn_off': {
                                'service': 'light.turn_off',
                                'entity_id': 'light.test_state'
                            },
                            'set_level': {
                                'service': 'light.turn_on',
                                'data_template': {
                                    'entity_id': 'light.test_state',
                                    'brightness': '{{brightness}}'
                                }
                            }
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_missing_off_does_not_create(self):
        """Test missing off."""
        with assert_setup_component(0, 'light'):
            assert setup.setup_component(self.hass, 'light', {
                'light': {
                    'platform': 'template',
                    'lights': {
                        'bad name here': {
                            'value_template': "{{ 1== 1}}",
                            'turn_on': {
                                'service': 'light.turn_on',
                                'entity_id': 'light.test_state'
                            },
                            'set_level': {
                                'service': 'light.turn_on',
                                'data_template': {
                                    'entity_id': 'light.test_state',
                                    'brightness': '{{brightness}}'
                                }
                            }
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_on_action(self):
        """Test on action."""
        assert setup.setup_component(self.hass, 'light', {
            'light': {
                'platform': 'template',
                'lights': {
                    'test_template_light': {
                        'value_template': "{{states.light.test_state.state}}",
                        'turn_on': {
                            'service': 'test.automation',
                        },
                        'turn_off': {
                            'service': 'light.turn_off',
                            'entity_id': 'light.test_state'
                        },
                        'set_level': {
                            'service': 'light.turn_on',
                            'data_template': {
                                'entity_id': 'light.test_state',
                                'brightness': '{{brightness}}'
                            }
                        }
                    }
                }
            }
        })

        self.hass.start()
        self.hass.block_till_done()

        self.hass.states.set('light.test_state', STATE_OFF)
        self.hass.block_till_done()

        state = self.hass.states.get('light.test_template_light')
        assert state.state == STATE_OFF

        core.light.turn_on(self.hass, 'light.test_template_light')
        self.hass.block_till_done()

        assert len(self.calls) == 1

    def test_on_action_optimistic(self):
        """Test on action with optimistic state."""
        assert setup.setup_component(self.hass, 'light', {
            'light': {
                'platform': 'template',
                'lights': {
                    'test_template_light': {
                        'turn_on': {
                            'service': 'test.automation',
                        },
                        'turn_off': {
                            'service': 'light.turn_off',
                            'entity_id': 'light.test_state'
                        },
                        'set_level': {
                            'service': 'light.turn_on',
                            'data_template': {
                                'entity_id': 'light.test_state',
                                'brightness': '{{brightness}}'
                            }
                        }
                    }
                }
            }
        })

        self.hass.start()
        self.hass.block_till_done()

        self.hass.states.set('light.test_state', STATE_OFF)
        self.hass.block_till_done()

        state = self.hass.states.get('light.test_template_light')
        assert state.state == STATE_OFF

        core.light.turn_on(self.hass, 'light.test_template_light')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test_template_light')
        assert len(self.calls) == 1
        assert state.state == STATE_ON

    def test_off_action(self):
        """Test off action."""
        assert setup.setup_component(self.hass, 'light', {
            'light': {
                'platform': 'template',
                'lights': {
                    'test_template_light': {
                        'value_template': "{{states.light.test_state.state}}",
                        'turn_on': {
                            'service': 'light.turn_on',
                            'entity_id': 'light.test_state'
                        },
                        'turn_off': {
                            'service': 'test.automation',
                        },
                        'set_level': {
                            'service': 'light.turn_on',
                            'data_template': {
                                'entity_id': 'light.test_state',
                                'brightness': '{{brightness}}'
                            }
                        }
                    }
                }
            }
        })

        self.hass.start()
        self.hass.block_till_done()

        self.hass.states.set('light.test_state', STATE_ON)
        self.hass.block_till_done()

        state = self.hass.states.get('light.test_template_light')
        assert state.state == STATE_ON

        core.light.turn_off(self.hass, 'light.test_template_light')
        self.hass.block_till_done()

        assert len(self.calls) == 1

    def test_off_action_optimistic(self):
        """Test off action with optimistic state."""
        assert setup.setup_component(self.hass, 'light', {
            'light': {
                'platform': 'template',
                'lights': {
                    'test_template_light': {
                        'turn_on': {
                            'service': 'light.turn_on',
                            'entity_id': 'light.test_state'
                        },
                        'turn_off': {
                            'service': 'test.automation',
                        },
                        'set_level': {
                            'service': 'light.turn_on',
                            'data_template': {
                                'entity_id': 'light.test_state',
                                'brightness': '{{brightness}}'
                            }
                        }
                    }
                }
            }
        })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('light.test_template_light')
        assert state.state == STATE_OFF

        core.light.turn_off(self.hass, 'light.test_template_light')
        self.hass.block_till_done()

        assert len(self.calls) == 1
        state = self.hass.states.get('light.test_template_light')
        assert state.state == STATE_OFF

    def test_level_action_no_template(self):
        """Test setting brightness with optimistic template."""
        assert setup.setup_component(self.hass, 'light', {
            'light': {
                'platform': 'template',
                'lights': {
                    'test_template_light': {
                        'value_template': '{{1 == 1}}',
                        'turn_on': {
                            'service': 'light.turn_on',
                            'entity_id': 'light.test_state'
                        },
                        'turn_off': {
                            'service': 'light.turn_off',
                            'entity_id': 'light.test_state'
                        },
                        'set_level': {
                            'service': 'test.automation',
                            'data_template': {
                                'entity_id': 'test.test_state',
                                'brightness': '{{brightness}}'
                            }
                        },
                    }
                }
            }
        })
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('light.test_template_light')
        assert state.attributes.get('brightness') is None

        core.light.turn_on(
            self.hass, 'light.test_template_light', **{ATTR_BRIGHTNESS: 124})
        self.hass.block_till_done()
        assert len(self.calls) == 1
        assert self.calls[0].data['brightness'] == '124'

        state = self.hass.states.get('light.test_template_light')
        _LOGGER.info(str(state.attributes))
        assert state is not None
        assert state.attributes.get('brightness') == 124

    def test_level_template(self):
        """Test the template for the level."""
        with assert_setup_component(1, 'light'):
            assert setup.setup_component(self.hass, 'light', {
                'light': {
                    'platform': 'template',
                    'lights': {
                        'test_template_light': {
                            'value_template': "{{ 1 == 1 }}",
                            'turn_on': {
                                'service': 'light.turn_on',
                                'entity_id': 'light.test_state'
                            },
                            'turn_off': {
                                'service': 'light.turn_off',
                                'entity_id': 'light.test_state'
                            },
                            'set_level': {
                                'service': 'light.turn_on',
                                'data_template': {
                                    'entity_id': 'light.test_state',
                                    'brightness': '{{brightness}}'
                                }
                            },
                            'level_template':
                                '{{42}}'
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('light.test_template_light')
        assert state is not None

        assert state.attributes.get('brightness') == 42

    def test_friendly_name(self):
        """Test the accessibility of the friendly_name attribute."""
        with assert_setup_component(1, 'light'):
            assert setup.setup_component(self.hass, 'light', {
                'light': {
                    'platform': 'template',
                    'lights': {
                        'test_template_light': {
                            'friendly_name': 'Template light',
                            'value_template': "{{ 1 == 1 }}",
                            'turn_on': {
                                'service': 'light.turn_on',
                                'entity_id': 'light.test_state'
                            },
                            'turn_off': {
                                'service': 'light.turn_off',
                                'entity_id': 'light.test_state'
                            },
                            'set_level': {
                                'service': 'light.turn_on',
                                'data_template': {
                                    'entity_id': 'light.test_state',
                                    'brightness': '{{brightness}}'
                                }
                            }
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('light.test_template_light')
        assert state is not None

        assert state.attributes.get('friendly_name') == 'Template light'

    def test_icon_template(self):
        """Test icon template."""
        with assert_setup_component(1, 'light'):
            assert setup.setup_component(self.hass, 'light', {
                'light': {
                    'platform': 'template',
                    'lights': {
                        'test_template_light': {
                            'friendly_name': 'Template light',
                            'value_template': "{{ 1 == 1 }}",
                            'turn_on': {
                                'service': 'light.turn_on',
                                'entity_id': 'light.test_state'
                            },
                            'turn_off': {
                                'service': 'light.turn_off',
                                'entity_id': 'light.test_state'
                            },
                            'set_level': {
                                'service': 'light.turn_on',
                                'data_template': {
                                    'entity_id': 'light.test_state',
                                    'brightness': '{{brightness}}'
                                }
                            },
                            'icon_template':
                                "{% if states.light.test_state.state %}"
                                "mdi:check"
                                "{% endif %}"
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('light.test_template_light')
        assert state.attributes.get('icon') == ''

        state = self.hass.states.set('light.test_state', STATE_ON)
        self.hass.block_till_done()

        state = self.hass.states.get('light.test_template_light')

        assert state.attributes['icon'] == 'mdi:check'

    def test_entity_picture_template(self):
        """Test entity_picture template."""
        with assert_setup_component(1, 'light'):
            assert setup.setup_component(self.hass, 'light', {
                'light': {
                    'platform': 'template',
                    'lights': {
                        'test_template_light': {
                            'friendly_name': 'Template light',
                            'value_template': "{{ 1 == 1 }}",
                            'turn_on': {
                                'service': 'light.turn_on',
                                'entity_id': 'light.test_state'
                            },
                            'turn_off': {
                                'service': 'light.turn_off',
                                'entity_id': 'light.test_state'
                            },
                            'set_level': {
                                'service': 'light.turn_on',
                                'data_template': {
                                    'entity_id': 'light.test_state',
                                    'brightness': '{{brightness}}'
                                }
                            },
                            'entity_picture_template':
                                "{% if states.light.test_state.state %}"
                                "/local/light.png"
                                "{% endif %}"
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('light.test_template_light')
        assert state.attributes.get('entity_picture') == ''

        state = self.hass.states.set('light.test_state', STATE_ON)
        self.hass.block_till_done()

        state = self.hass.states.get('light.test_template_light')

        assert state.attributes['entity_picture'] == '/local/light.png'
