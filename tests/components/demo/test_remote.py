"""The tests for the demo remote component."""
# pylint: disable=protected-access
import unittest

import homeassistant.components.remote as remote
from homeassistant.components.remote import ATTR_COMMAND
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant

ENTITY_ID = "remote.remote_one"
SERVICE_SEND_COMMAND = "send_command"


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
        self.hass.services.call(
            remote.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}
        )
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_ID)
        assert state.state == STATE_ON

        self.hass.services.call(
            remote.DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}
        )
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_ID)
        assert state.state == STATE_OFF

        self.hass.services.call(
            remote.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}
        )
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_ID)
        assert state.state == STATE_ON

        data = {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_COMMAND: ["test"],
        }

        self.hass.services.call(remote.DOMAIN, SERVICE_SEND_COMMAND, data)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_ID)
        assert state.attributes == {
            "friendly_name": "Remote One",
            "last_command_sent": "test",
            "supported_features": 0,
        }
