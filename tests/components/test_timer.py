"""The tests for the timer component."""
# pylint: disable=protected-access
import asyncio
import unittest
import logging

from homeassistant.core import CoreState, State
from homeassistant.setup import setup_component, async_setup_component
from homeassistant.components.timer import (
    DOMAIN, sync_start, pause, cancel, finish, CONF_SECONDS, CONF_NAME,
    CONF_ICON)
from homeassistant.const import (ATTR_ICON, ATTR_FRIENDLY_NAME)

from tests.common import (get_test_home_assistant, mock_restore_cache)

_LOGGER = logging.getLogger(__name__)


class TestTimer(unittest.TestCase):
    """Test the timer component."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_config(self):
        """Test config."""
        invalid_configs = [
            None,
            1,
            {},
            {'name with space': None},
        ]

        for cfg in invalid_configs:
            self.assertFalse(
                setup_component(self.hass, DOMAIN, {DOMAIN: cfg}))

    def test_methods(self):
        """Test start, pause, cancel and finish methods."""
        config = {
            DOMAIN: {
                'test_1': {
                    CONF_SECONDS: 10
                },
            }
        }

        assert setup_component(self.hass, 'timer', config)

        entity_id = 'timer.test_1'

        state = self.hass.states.get(entity_id)
        self.assertEqual(0, int(state.state))

    def test_methods_with_config(self):
        """Test increment, decrement, and reset methods with configuration."""
        config = {
            DOMAIN: {
                'test_2': {
                    CONF_NAME: 'MyTimer',
                    CONF_SECONDS: 10,
                }
            }
        }

        assert setup_component(self.hass, 'timer', config)

        entity_id = 'timer.test_2'

        state = self.hass.states.get(entity_id)
        self.assertEqual(0, int(state.state))

    def test_config_options(self):
        """Test configuration options."""
        count_start = len(self.hass.states.entity_ids())

        _LOGGER.debug('ENTITIES @ start: %s', self.hass.states.entity_ids())

        config = {
            DOMAIN: {
                'test_1': {},
                'test_2': {
                    CONF_NAME: 'Hello World',
                    CONF_ICON: 'mdi:work',
                    CONF_SECONDS: 10,
                }
            }
        }

        assert setup_component(self.hass, 'timer', config)
        self.hass.block_till_done()

        _LOGGER.debug('ENTITIES: %s', self.hass.states.entity_ids())

        self.assertEqual(count_start + 2, len(self.hass.states.entity_ids()))
        self.hass.block_till_done()

        state_1 = self.hass.states.get('timer.test_1')
        state_2 = self.hass.states.get('timer.test_2')

        self.assertIsNotNone(state_1)
        self.assertIsNotNone(state_2)

        #self.assertEqual(0, int(state_1.state))
        self.assertNotIn(ATTR_ICON, state_1.attributes)
        self.assertNotIn(ATTR_FRIENDLY_NAME, state_1.attributes)

        #self.assertEqual(10, int(state_2.state))
        self.assertEqual('Hello World',
                         state_2.attributes.get(ATTR_FRIENDLY_NAME))
        self.assertEqual('mdi:work', state_2.attributes.get(ATTR_ICON))


@asyncio.coroutine
def test_no_initial_state_and_no_restore_state(hass):
    """Ensure that entity is create without initial and restore feature."""
    hass.state = CoreState.starting

    yield from async_setup_component(hass, DOMAIN, {
        DOMAIN: {
            'test1': {
                CONF_SECONDS: 5,
            }
        }})

    state = hass.states.get('timer.test1')
    assert state
    assert int(state.state) == 0
