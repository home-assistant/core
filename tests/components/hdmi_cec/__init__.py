"""Tests for the HDMI-CEC component."""

from unittest.mock import AsyncMock, Mock

from homeassistant.components.hdmi_cec import KeyPressCommand, KeyReleaseCommand


class MockHDMIDevice:
    """Mock of a HDMIDevice."""

    def __init__(self, *, logical_address, **values):
        """Mock of a HDMIDevice."""
        self.set_update_callback = Mock(side_effect=self._set_update_callback)
        self.logical_address = logical_address
        self.name = f"hdmi_{logical_address:x}"
        if "power_status" not in values:
            # Default to invalid state.
            values["power_status"] = -1
        self._values = values
        self.turn_on = Mock()
        self.turn_off = Mock()
        self.send_command = Mock()
        self.async_send_command = AsyncMock()

    def __getattr__(self, name):
        """Get attribute from `_values` if not explicitly set."""
        return self._values.get(name)

    def __setattr__(self, name, value):
        """Set attributes in `_values` if not one of the known attributes."""
        if name in ("power_status", "status"):
            self._values[name] = value
            self._update()
        else:
            super().__setattr__(name, value)

    def _set_update_callback(self, update):
        self._update = update


def assert_key_press_release(fnc, count=0, *, dst, key):
    """Assert that correct KeyPressCommand & KeyReleaseCommand where sent."""
    assert fnc.call_count >= count * 2 + 1
    press_arg = fnc.call_args_list[count * 2].args[0]
    release_arg = fnc.call_args_list[count * 2 + 1].args[0]
    assert isinstance(press_arg, KeyPressCommand)
    assert press_arg.key == key
    assert press_arg.dst == dst
    assert isinstance(release_arg, KeyReleaseCommand)
    assert release_arg.dst == dst
