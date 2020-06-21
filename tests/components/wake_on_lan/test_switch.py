"""The tests for the wake on lan switch platform."""
import unittest

import homeassistant.components.switch as switch
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.setup import setup_component

from tests.async_mock import patch
from tests.common import get_test_home_assistant, mock_service
from tests.components.switch import common

TEST_STATE = None


def send_magic_packet(*macs, **kwargs):
    """Fake call for sending magic packets."""
    return


def call(cmd, stdout, stderr):
    """Return fake subprocess return codes."""
    if cmd[5] == "validhostname" and TEST_STATE:
        return 0
    return 2


def system():
    """Fake system call to test the windows platform."""
    return "Windows"


class TestWolSwitch(unittest.TestCase):
    """Test the wol switch."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.addCleanup(self.hass.stop)

    @patch("wakeonlan.send_magic_packet", new=send_magic_packet)
    @patch("subprocess.call", new=call)
    def test_valid_hostname(self):
        """Test with valid hostname."""
        global TEST_STATE
        TEST_STATE = False
        assert setup_component(
            self.hass,
            switch.DOMAIN,
            {
                "switch": {
                    "platform": "wake_on_lan",
                    "mac": "00-01-02-03-04-05",
                    "host": "validhostname",
                }
            },
        )
        self.hass.block_till_done()

        state = self.hass.states.get("switch.wake_on_lan")
        assert STATE_OFF == state.state

        TEST_STATE = True

        common.turn_on(self.hass, "switch.wake_on_lan")
        self.hass.block_till_done()

        state = self.hass.states.get("switch.wake_on_lan")
        assert STATE_ON == state.state

        common.turn_off(self.hass, "switch.wake_on_lan")
        self.hass.block_till_done()

        state = self.hass.states.get("switch.wake_on_lan")
        assert STATE_ON == state.state

    @patch("wakeonlan.send_magic_packet", new=send_magic_packet)
    @patch("subprocess.call", new=call)
    @patch("platform.system", new=system)
    def test_valid_hostname_windows(self):
        """Test with valid hostname on windows."""
        global TEST_STATE
        TEST_STATE = False
        assert setup_component(
            self.hass,
            switch.DOMAIN,
            {
                "switch": {
                    "platform": "wake_on_lan",
                    "mac": "00-01-02-03-04-05",
                    "host": "validhostname",
                }
            },
        )
        self.hass.block_till_done()

        state = self.hass.states.get("switch.wake_on_lan")
        assert STATE_OFF == state.state

        TEST_STATE = True

        common.turn_on(self.hass, "switch.wake_on_lan")
        self.hass.block_till_done()

        state = self.hass.states.get("switch.wake_on_lan")
        assert STATE_ON == state.state

    @patch("wakeonlan.send_magic_packet", new=send_magic_packet)
    @patch("subprocess.call", new=call)
    def test_minimal_config(self):
        """Test with minimal config."""
        assert setup_component(
            self.hass,
            switch.DOMAIN,
            {"switch": {"platform": "wake_on_lan", "mac": "00-01-02-03-04-05"}},
        )

    @patch("wakeonlan.send_magic_packet", new=send_magic_packet)
    @patch("subprocess.call", new=call)
    def test_broadcast_config(self):
        """Test with broadcast address config."""
        assert setup_component(
            self.hass,
            switch.DOMAIN,
            {
                "switch": {
                    "platform": "wake_on_lan",
                    "mac": "00-01-02-03-04-05",
                    "broadcast_address": "255.255.255.255",
                    "broadcast_port": 999,
                }
            },
        )
        self.hass.block_till_done()

        state = self.hass.states.get("switch.wake_on_lan")
        assert STATE_OFF == state.state

        common.turn_on(self.hass, "switch.wake_on_lan")
        self.hass.block_till_done()

    @patch("wakeonlan.send_magic_packet", new=send_magic_packet)
    @patch("subprocess.call", new=call)
    def test_off_script(self):
        """Test with turn off script."""
        global TEST_STATE
        TEST_STATE = False
        assert setup_component(
            self.hass,
            switch.DOMAIN,
            {
                "switch": {
                    "platform": "wake_on_lan",
                    "mac": "00-01-02-03-04-05",
                    "host": "validhostname",
                    "turn_off": {"service": "shell_command.turn_off_target"},
                }
            },
        )
        self.hass.block_till_done()
        calls = mock_service(self.hass, "shell_command", "turn_off_target")

        state = self.hass.states.get("switch.wake_on_lan")
        assert STATE_OFF == state.state

        TEST_STATE = True

        common.turn_on(self.hass, "switch.wake_on_lan")
        self.hass.block_till_done()

        state = self.hass.states.get("switch.wake_on_lan")
        assert STATE_ON == state.state
        assert len(calls) == 0

        TEST_STATE = False

        common.turn_off(self.hass, "switch.wake_on_lan")
        self.hass.block_till_done()

        state = self.hass.states.get("switch.wake_on_lan")
        assert STATE_OFF == state.state
        assert len(calls) == 1

    @patch("wakeonlan.send_magic_packet", new=send_magic_packet)
    @patch("subprocess.call", new=call)
    @patch("platform.system", new=system)
    def test_invalid_hostname_windows(self):
        """Test with invalid hostname on windows."""
        global TEST_STATE
        TEST_STATE = False
        assert setup_component(
            self.hass,
            switch.DOMAIN,
            {
                "switch": {
                    "platform": "wake_on_lan",
                    "mac": "00-01-02-03-04-05",
                    "host": "invalidhostname",
                }
            },
        )
        self.hass.block_till_done()

        state = self.hass.states.get("switch.wake_on_lan")
        assert STATE_OFF == state.state

        TEST_STATE = True

        common.turn_on(self.hass, "switch.wake_on_lan")
        self.hass.block_till_done()

        state = self.hass.states.get("switch.wake_on_lan")
        assert STATE_OFF == state.state
