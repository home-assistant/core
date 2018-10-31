"""The tests the cover command line platform."""
import logging
import unittest

from homeassistant import setup
from homeassistant.core import callback
from homeassistant.components.cover import (
    ATTR_POSITION, ATTR_TILT_POSITION, DOMAIN)
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_CLOSE_COVER, SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER, SERVICE_OPEN_COVER_TILT, SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION, SERVICE_STOP_COVER,
    STATE_CLOSED, STATE_OPEN)

from tests.common import (
    get_test_home_assistant, assert_setup_component)

_LOGGER = logging.getLogger(__name__)

ENTITY_COVER = 'cover.test_template_cover'


class TestTemplateCover(unittest.TestCase):
    """Test the cover command line platform."""

    hass = None
    calls = None
    # pylint: disable=invalid-name

    def setup_method(self, method):
        """Initialize services when tests are started."""
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
        with assert_setup_component(1, 'cover'):
            assert setup.setup_component(self.hass, 'cover', {
                'cover': {
                    'platform': 'template',
                    'covers': {
                        'test_template_cover': {
                            'value_template':
                                "{{ states.cover.test_state.state }}",
                            'open_cover': {
                                'service': 'cover.open_cover',
                                'entity_id': 'cover.test_state'
                            },
                            'close_cover': {
                                'service': 'cover.close_cover',
                                'entity_id': 'cover.test_state'
                            },
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.set('cover.test_state', STATE_OPEN)
        self.hass.block_till_done()

        state = self.hass.states.get('cover.test_template_cover')
        assert state.state == STATE_OPEN

        state = self.hass.states.set('cover.test_state', STATE_CLOSED)
        self.hass.block_till_done()

        state = self.hass.states.get('cover.test_template_cover')
        assert state.state == STATE_CLOSED

    def test_template_state_boolean(self):
        """Test the value_template attribute."""
        with assert_setup_component(1, 'cover'):
            assert setup.setup_component(self.hass, 'cover', {
                'cover': {
                    'platform': 'template',
                    'covers': {
                        'test_template_cover': {
                            'value_template':
                                "{{ 1 == 1 }}",
                            'open_cover': {
                                'service': 'cover.open_cover',
                                'entity_id': 'cover.test_state'
                            },
                            'close_cover': {
                                'service': 'cover.close_cover',
                                'entity_id': 'cover.test_state'
                            },
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('cover.test_template_cover')
        assert state.state == STATE_OPEN

    def test_template_position(self):
        """Test the position_template attribute."""
        with assert_setup_component(1, 'cover'):
            assert setup.setup_component(self.hass, 'cover', {
                'cover': {
                    'platform': 'template',
                    'covers': {
                        'test_template_cover': {
                            'position_template':
                                "{{ states.cover.test.attributes.position }}",
                            'open_cover': {
                                'service': 'cover.open_cover',
                                'entity_id': 'cover.test'
                            },
                            'close_cover': {
                                'service': 'cover.close_cover',
                                'entity_id': 'cover.test'
                            },
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.set('cover.test', STATE_CLOSED)
        self.hass.block_till_done()

        entity = self.hass.states.get('cover.test')
        attrs = dict()
        attrs['position'] = 42
        self.hass.states.set(
            entity.entity_id, entity.state,
            attributes=attrs)
        self.hass.block_till_done()

        state = self.hass.states.get('cover.test_template_cover')
        assert state.attributes.get('current_position') == 42.0
        assert state.state == STATE_OPEN

        state = self.hass.states.set('cover.test', STATE_OPEN)
        self.hass.block_till_done()
        entity = self.hass.states.get('cover.test')
        attrs['position'] = 0.0
        self.hass.states.set(
            entity.entity_id, entity.state,
            attributes=attrs)
        self.hass.block_till_done()

        state = self.hass.states.get('cover.test_template_cover')
        assert state.attributes.get('current_position') == 0.0
        assert state.state == STATE_CLOSED

    def test_template_tilt(self):
        """Test the tilt_template attribute."""
        with assert_setup_component(1, 'cover'):
            assert setup.setup_component(self.hass, 'cover', {
                'cover': {
                    'platform': 'template',
                    'covers': {
                        'test_template_cover': {
                            'value_template':
                                "{{ 1 == 1 }}",
                            'tilt_template':
                                "{{ 42 }}",
                            'open_cover': {
                                'service': 'cover.open_cover',
                                'entity_id': 'cover.test_state'
                            },
                            'close_cover': {
                                'service': 'cover.close_cover',
                                'entity_id': 'cover.test_state'
                            },
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('cover.test_template_cover')
        assert state.attributes.get('current_tilt_position') == 42.0

    def test_template_out_of_bounds(self):
        """Test template out-of-bounds condition."""
        with assert_setup_component(1, 'cover'):
            assert setup.setup_component(self.hass, 'cover', {
                'cover': {
                    'platform': 'template',
                    'covers': {
                        'test_template_cover': {
                            'position_template':
                                "{{ -1 }}",
                            'tilt_template':
                                "{{ 110 }}",
                            'open_cover': {
                                'service': 'cover.open_cover',
                                'entity_id': 'cover.test_state'
                            },
                            'close_cover': {
                                'service': 'cover.close_cover',
                                'entity_id': 'cover.test_state'
                            },
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('cover.test_template_cover')
        assert state.attributes.get('current_tilt_position') is None
        assert state.attributes.get('current_position') is None

    def test_template_mutex(self):
        """Test that only value or position template can be used."""
        with assert_setup_component(0, 'cover'):
            assert setup.setup_component(self.hass, 'cover', {
                'cover': {
                    'platform': 'template',
                    'covers': {
                        'test_template_cover': {
                            'value_template':
                                "{{ 1 == 1 }}",
                            'position_template':
                                "{{ 42 }}",
                            'open_cover': {
                                'service': 'cover.open_cover',
                                'entity_id': 'cover.test_state'
                            },
                            'close_cover': {
                                'service': 'cover.close_cover',
                                'entity_id': 'cover.test_state'
                            },
                            'icon_template':
                                "{% if states.cover.test_state.state %}"
                                "mdi:check"
                                "{% endif %}"
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_template_open_or_position(self):
        """Test that at least one of open_cover or set_position is used."""
        with assert_setup_component(1, 'cover'):
            assert setup.setup_component(self.hass, 'cover', {
                'cover': {
                    'platform': 'template',
                    'covers': {
                        'test_template_cover': {
                            'value_template':
                                "{{ 1 == 1 }}",
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_template_open_and_close(self):
        """Test that if open_cover is specified, close_cover is too."""
        with assert_setup_component(0, 'cover'):
            assert setup.setup_component(self.hass, 'cover', {
                'cover': {
                    'platform': 'template',
                    'covers': {
                        'test_template_cover': {
                            'value_template':
                                "{{ 1 == 1 }}",
                            'open_cover': {
                                'service': 'cover.open_cover',
                                'entity_id': 'cover.test_state'
                            },
                        },
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        assert self.hass.states.all() == []

    def test_template_non_numeric(self):
        """Test that tilt_template values are numeric."""
        with assert_setup_component(1, 'cover'):
            assert setup.setup_component(self.hass, 'cover', {
                'cover': {
                    'platform': 'template',
                    'covers': {
                        'test_template_cover': {
                            'position_template':
                                "{{ on }}",
                            'tilt_template':
                                "{% if states.cover.test_state.state %}"
                                "on"
                                "{% else %}"
                                "off"
                                "{% endif %}",
                            'open_cover': {
                                'service': 'cover.open_cover',
                                'entity_id': 'cover.test_state'
                            },
                            'close_cover': {
                                'service': 'cover.close_cover',
                                'entity_id': 'cover.test_state'
                            },
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('cover.test_template_cover')
        assert state.attributes.get('current_tilt_position') is None
        assert state.attributes.get('current_position') is None

    def test_open_action(self):
        """Test the open_cover command."""
        with assert_setup_component(1, 'cover'):
            assert setup.setup_component(self.hass, 'cover', {
                'cover': {
                    'platform': 'template',
                    'covers': {
                        'test_template_cover': {
                            'position_template':
                                "{{ 0 }}",
                            'open_cover': {
                                'service': 'test.automation',
                            },
                            'close_cover': {
                                'service': 'cover.close_cover',
                                'entity_id': 'cover.test_state'
                            },
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('cover.test_template_cover')
        assert state.state == STATE_CLOSED

        self.hass.services.call(
            DOMAIN, SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True)
        self.hass.block_till_done()

        assert len(self.calls) == 1

    def test_close_stop_action(self):
        """Test the close-cover and stop_cover commands."""
        with assert_setup_component(1, 'cover'):
            assert setup.setup_component(self.hass, 'cover', {
                'cover': {
                    'platform': 'template',
                    'covers': {
                        'test_template_cover': {
                            'position_template':
                                "{{ 100 }}",
                            'open_cover': {
                                'service': 'cover.open_cover',
                                'entity_id': 'cover.test_state'
                            },
                            'close_cover': {
                                'service': 'test.automation',
                            },
                            'stop_cover': {
                                'service': 'test.automation',
                            },
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('cover.test_template_cover')
        assert state.state == STATE_OPEN

        self.hass.services.call(
            DOMAIN, SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True)
        self.hass.block_till_done()

        self.hass.services.call(
            DOMAIN, SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True)
        self.hass.block_till_done()

        assert len(self.calls) == 2

    def test_set_position(self):
        """Test the set_position command."""
        with assert_setup_component(1, 'cover'):
            assert setup.setup_component(self.hass, 'input_number', {
               'input_number': {
                   'test': {
                       'min': '0',
                       'max': '100',
                       'initial': '42',
                   }
               }
            })
            assert setup.setup_component(self.hass, 'cover', {
                'cover': {
                    'platform': 'template',
                    'covers': {
                        'test_template_cover': {
                            'position_template':
                                "{{ states.input_number.test.state | int }}",
                            'set_cover_position': {
                                'service': 'input_number.set_value',
                                'entity_id': 'input_number.test',
                                'data_template': {
                                    'value': '{{ position }}'
                                },
                            },
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.set('input_number.test', 42)
        self.hass.block_till_done()
        state = self.hass.states.get('cover.test_template_cover')
        assert state.state == STATE_OPEN

        self.hass.services.call(
            DOMAIN, SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True)
        self.hass.block_till_done()
        state = self.hass.states.get('cover.test_template_cover')
        assert state.attributes.get('current_position') == 100.0

        self.hass.services.call(
            DOMAIN, SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True)
        self.hass.block_till_done()
        state = self.hass.states.get('cover.test_template_cover')
        assert state.attributes.get('current_position') == 0.0

        self.hass.services.call(
            DOMAIN, SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: ENTITY_COVER, ATTR_POSITION: 25}, blocking=True)
        self.hass.block_till_done()
        state = self.hass.states.get('cover.test_template_cover')
        assert state.attributes.get('current_position') == 25.0

    def test_set_tilt_position(self):
        """Test the set_tilt_position command."""
        with assert_setup_component(1, 'cover'):
            assert setup.setup_component(self.hass, 'cover', {
                'cover': {
                    'platform': 'template',
                    'covers': {
                        'test_template_cover': {
                            'position_template':
                                "{{ 100 }}",
                            'open_cover': {
                                'service': 'cover.open_cover',
                                'entity_id': 'cover.test_state'
                            },
                            'close_cover': {
                                'service': 'cover.close_cover',
                                'entity_id': 'cover.test_state'
                            },
                            'set_cover_tilt_position': {
                                'service': 'test.automation',
                            },
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        self.hass.services.call(
            DOMAIN, SERVICE_SET_COVER_TILT_POSITION,
            {ATTR_ENTITY_ID: ENTITY_COVER, ATTR_TILT_POSITION: 42},
            blocking=True)
        self.hass.block_till_done()

        assert len(self.calls) == 1

    def test_open_tilt_action(self):
        """Test the open_cover_tilt command."""
        with assert_setup_component(1, 'cover'):
            assert setup.setup_component(self.hass, 'cover', {
                'cover': {
                    'platform': 'template',
                    'covers': {
                        'test_template_cover': {
                            'position_template':
                                "{{ 100 }}",
                            'open_cover': {
                                'service': 'cover.open_cover',
                                'entity_id': 'cover.test_state'
                            },
                            'close_cover': {
                                'service': 'cover.close_cover',
                                'entity_id': 'cover.test_state'
                            },
                            'set_cover_tilt_position': {
                                'service': 'test.automation',
                            },
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        self.hass.services.call(
            DOMAIN, SERVICE_OPEN_COVER_TILT,
            {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True)
        self.hass.block_till_done()

        assert len(self.calls) == 1

    def test_close_tilt_action(self):
        """Test the close_cover_tilt command."""
        with assert_setup_component(1, 'cover'):
            assert setup.setup_component(self.hass, 'cover', {
                'cover': {
                    'platform': 'template',
                    'covers': {
                        'test_template_cover': {
                            'position_template':
                                "{{ 100 }}",
                            'open_cover': {
                                'service': 'cover.open_cover',
                                'entity_id': 'cover.test_state'
                            },
                            'close_cover': {
                                'service': 'cover.close_cover',
                                'entity_id': 'cover.test_state'
                            },
                            'set_cover_tilt_position': {
                                'service': 'test.automation',
                            },
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        self.hass.services.call(
            DOMAIN, SERVICE_CLOSE_COVER_TILT,
            {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True)
        self.hass.block_till_done()

        assert len(self.calls) == 1

    def test_set_position_optimistic(self):
        """Test optimistic position mode."""
        with assert_setup_component(1, 'cover'):
            assert setup.setup_component(self.hass, 'cover', {
                'cover': {
                    'platform': 'template',
                    'covers': {
                        'test_template_cover': {
                            'set_cover_position': {
                                'service': 'test.automation',
                            },
                        }
                    }
                }
            })
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('cover.test_template_cover')
        assert state.attributes.get('current_position') is None

        self.hass.services.call(
            DOMAIN, SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: ENTITY_COVER, ATTR_POSITION: 42}, blocking=True)
        self.hass.block_till_done()
        state = self.hass.states.get('cover.test_template_cover')
        assert state.attributes.get('current_position') == 42.0

        self.hass.services.call(
            DOMAIN, SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True)
        self.hass.block_till_done()
        state = self.hass.states.get('cover.test_template_cover')
        assert state.state == STATE_CLOSED

        self.hass.services.call(
            DOMAIN, SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True)
        self.hass.block_till_done()
        state = self.hass.states.get('cover.test_template_cover')
        assert state.state == STATE_OPEN

    def test_set_tilt_position_optimistic(self):
        """Test the optimistic tilt_position mode."""
        with assert_setup_component(1, 'cover'):
            assert setup.setup_component(self.hass, 'cover', {
                'cover': {
                    'platform': 'template',
                    'covers': {
                        'test_template_cover': {
                            'position_template':
                                "{{ 100 }}",
                            'set_cover_position': {
                                'service': 'test.automation',
                            },
                            'set_cover_tilt_position': {
                                'service': 'test.automation',
                            },
                        }
                    }
                }
            })
        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('cover.test_template_cover')
        assert state.attributes.get('current_tilt_position') is None

        self.hass.services.call(
            DOMAIN, SERVICE_SET_COVER_TILT_POSITION,
            {ATTR_ENTITY_ID: ENTITY_COVER, ATTR_TILT_POSITION: 42},
            blocking=True)
        self.hass.block_till_done()
        state = self.hass.states.get('cover.test_template_cover')
        assert state.attributes.get('current_tilt_position') == 42.0

        self.hass.services.call(
            DOMAIN, SERVICE_CLOSE_COVER_TILT,
            {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True)
        self.hass.block_till_done()
        state = self.hass.states.get('cover.test_template_cover')
        assert state.attributes.get('current_tilt_position') == 0.0

        self.hass.services.call(
            DOMAIN, SERVICE_OPEN_COVER_TILT,
            {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True)
        self.hass.block_till_done()
        state = self.hass.states.get('cover.test_template_cover')
        assert state.attributes.get('current_tilt_position') == 100.0

    def test_icon_template(self):
        """Test icon template."""
        with assert_setup_component(1, 'cover'):
            assert setup.setup_component(self.hass, 'cover', {
                'cover': {
                    'platform': 'template',
                    'covers': {
                        'test_template_cover': {
                            'value_template':
                                "{{ states.cover.test_state.state }}",
                            'open_cover': {
                                'service': 'cover.open_cover',
                                'entity_id': 'cover.test_state'
                            },
                            'close_cover': {
                                'service': 'cover.close_cover',
                                'entity_id': 'cover.test_state'
                            },
                            'icon_template':
                                "{% if states.cover.test_state.state %}"
                                "mdi:check"
                                "{% endif %}"
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('cover.test_template_cover')
        assert state.attributes.get('icon') == ''

        state = self.hass.states.set('cover.test_state', STATE_OPEN)
        self.hass.block_till_done()

        state = self.hass.states.get('cover.test_template_cover')

        assert state.attributes['icon'] == 'mdi:check'

    def test_entity_picture_template(self):
        """Test icon template."""
        with assert_setup_component(1, 'cover'):
            assert setup.setup_component(self.hass, 'cover', {
                'cover': {
                    'platform': 'template',
                    'covers': {
                        'test_template_cover': {
                            'value_template':
                                "{{ states.cover.test_state.state }}",
                            'open_cover': {
                                'service': 'cover.open_cover',
                                'entity_id': 'cover.test_state'
                            },
                            'close_cover': {
                                'service': 'cover.close_cover',
                                'entity_id': 'cover.test_state'
                            },
                            'entity_picture_template':
                                "{% if states.cover.test_state.state %}"
                                "/local/cover.png"
                                "{% endif %}"
                        }
                    }
                }
            })

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get('cover.test_template_cover')
        assert state.attributes.get('entity_picture') == ''

        state = self.hass.states.set('cover.test_state', STATE_OPEN)
        self.hass.block_till_done()

        state = self.hass.states.get('cover.test_template_cover')

        assert state.attributes['entity_picture'] == '/local/cover.png'
