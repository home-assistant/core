"""The tests for the demo remote component."""
# pylint: disable=protected-access
import unittest

import homeassistant.components.remote as remote
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant
from tests.components.remote import common

ENTITY_ID = "remote.remote_one"


class TestDemoRemote(unittest.TestCase):
    """Test the demo remote."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        assert setup_component(
            self.hass, remote.DOMAIN, {"remote": {"platform": "demo"}}
        )
        self.hass.block_till_done()

        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_methods(self):
        """Test if services call the entity methods as expected."""
        common.turn_on(self.hass, entity_id=ENTITY_ID)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_ID)
        assert state.state == STATE_ON

        common.turn_off(self.hass, entity_id=ENTITY_ID)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_ID)
        assert state.state == STATE_OFF

        common.turn_on(self.hass, entity_id=ENTITY_ID)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_ID)
        assert state.state == STATE_ON

        common.send_command(self.hass, "test", entity_id=ENTITY_ID)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_ID)
        assert state.attributes == {
            "friendly_name": "Remote One",
            "last_command_sent": "test",
            "supported_features": 0,
        }
