"""The tests for the Command line switch platform."""
import json
import os
import tempfile
import unittest

import homeassistant.components.command_line.switch as command_line
import homeassistant.components.switch as switch
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant
from tests.components.switch import common


# pylint: disable=invalid-name
class TestCommandSwitch(unittest.TestCase):
    """Test the command switch."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_state_none(self):
        """Test with none state."""
        with tempfile.TemporaryDirectory() as tempdirname:
            path = os.path.join(tempdirname, "switch_status")
            test_switch = {
                "command_on": f"echo 1 > {path}",
                "command_off": f"echo 0 > {path}",
            }
            assert setup_component(
                self.hass,
                switch.DOMAIN,
                {
                    "switch": {
                        "platform": "command_line",
                        "switches": {"test": test_switch},
                    }
                },
            )

            state = self.hass.states.get("switch.test")
            assert STATE_OFF == state.state

            common.turn_on(self.hass, "switch.test")
            self.hass.block_till_done()

            state = self.hass.states.get("switch.test")
            assert STATE_ON == state.state

            common.turn_off(self.hass, "switch.test")
            self.hass.block_till_done()

            state = self.hass.states.get("switch.test")
            assert STATE_OFF == state.state

    def test_state_value(self):
        """Test with state value."""
        with tempfile.TemporaryDirectory() as tempdirname:
            path = os.path.join(tempdirname, "switch_status")
            test_switch = {
                "command_state": f"cat {path}",
                "command_on": f"echo 1 > {path}",
                "command_off": f"echo 0 > {path}",
                "value_template": '{{ value=="1" }}',
            }
            assert setup_component(
                self.hass,
                switch.DOMAIN,
                {
                    "switch": {
                        "platform": "command_line",
                        "switches": {"test": test_switch},
                    }
                },
            )

            state = self.hass.states.get("switch.test")
            assert STATE_OFF == state.state

            common.turn_on(self.hass, "switch.test")
            self.hass.block_till_done()

            state = self.hass.states.get("switch.test")
            assert STATE_ON == state.state

            common.turn_off(self.hass, "switch.test")
            self.hass.block_till_done()

            state = self.hass.states.get("switch.test")
            assert STATE_OFF == state.state

    def test_state_json_value(self):
        """Test with state JSON value."""
        with tempfile.TemporaryDirectory() as tempdirname:
            path = os.path.join(tempdirname, "switch_status")
            oncmd = json.dumps({"status": "ok"})
            offcmd = json.dumps({"status": "nope"})
            test_switch = {
                "command_state": f"cat {path}",
                "command_on": f"echo '{oncmd}' > {path}",
                "command_off": f"echo '{offcmd}' > {path}",
                "value_template": '{{ value_json.status=="ok" }}',
            }
            assert setup_component(
                self.hass,
                switch.DOMAIN,
                {
                    "switch": {
                        "platform": "command_line",
                        "switches": {"test": test_switch},
                    }
                },
            )

            state = self.hass.states.get("switch.test")
            assert STATE_OFF == state.state

            common.turn_on(self.hass, "switch.test")
            self.hass.block_till_done()

            state = self.hass.states.get("switch.test")
            assert STATE_ON == state.state

            common.turn_off(self.hass, "switch.test")
            self.hass.block_till_done()

            state = self.hass.states.get("switch.test")
            assert STATE_OFF == state.state

    def test_state_code(self):
        """Test with state code."""
        with tempfile.TemporaryDirectory() as tempdirname:
            path = os.path.join(tempdirname, "switch_status")
            test_switch = {
                "command_state": f"cat {path}",
                "command_on": f"echo 1 > {path}",
                "command_off": f"echo 0 > {path}",
            }
            assert setup_component(
                self.hass,
                switch.DOMAIN,
                {
                    "switch": {
                        "platform": "command_line",
                        "switches": {"test": test_switch},
                    }
                },
            )

            state = self.hass.states.get("switch.test")
            assert STATE_OFF == state.state

            common.turn_on(self.hass, "switch.test")
            self.hass.block_till_done()

            state = self.hass.states.get("switch.test")
            assert STATE_ON == state.state

            common.turn_off(self.hass, "switch.test")
            self.hass.block_till_done()

            state = self.hass.states.get("switch.test")
            assert STATE_ON == state.state

    def test_assumed_state_should_be_true_if_command_state_is_none(self):
        """Test with state value."""
        # args: hass, device_name, friendly_name, command_on, command_off,
        #       command_state, value_template
        init_args = [
            self.hass,
            "test_device_name",
            "Test friendly name!",
            "echo 'on command'",
            "echo 'off command'",
            None,
            None,
        ]

        no_state_device = command_line.CommandSwitch(*init_args)
        assert no_state_device.assumed_state

        # Set state command
        init_args[-2] = "cat {}"

        state_device = command_line.CommandSwitch(*init_args)
        assert not state_device.assumed_state

    def test_entity_id_set_correctly(self):
        """Test that entity_id is set correctly from object_id."""
        init_args = [
            self.hass,
            "test_device_name",
            "Test friendly name!",
            "echo 'on command'",
            "echo 'off command'",
            False,
            None,
        ]

        test_switch = command_line.CommandSwitch(*init_args)
        assert test_switch.entity_id == "switch.test_device_name"
        assert test_switch.name == "Test friendly name!"
