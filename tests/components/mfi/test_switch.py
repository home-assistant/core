"""The tests for the mFi switch platform."""
import unittest

import homeassistant.components.mfi.switch as mfi
import homeassistant.components.switch as switch
from homeassistant.setup import setup_component

import tests.async_mock as mock
from tests.common import get_test_home_assistant


class TestMfiSwitchSetup(unittest.TestCase):
    """Test the mFi switch."""

    PLATFORM = mfi
    COMPONENT = switch
    THING = "switch"
    GOOD_CONFIG = {
        "switch": {
            "platform": "mfi",
            "host": "foo",
            "port": 6123,
            "username": "user",
            "password": "pass",
            "ssl": True,
            "verify_ssl": True,
        }
    }

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    @mock.patch("homeassistant.components.mfi.switch.MFiClient")
    @mock.patch("homeassistant.components.mfi.switch.MfiSwitch")
    def test_setup_adds_proper_devices(self, mock_switch, mock_client):
        """Test if setup adds devices."""
        ports = {
            i: mock.MagicMock(model=model) for i, model in enumerate(mfi.SWITCH_MODELS)
        }
        ports["bad"] = mock.MagicMock(model="notaswitch")
        print(ports["bad"].model)
        mock_client.return_value.get_devices.return_value = [
            mock.MagicMock(ports=ports)
        ]
        assert setup_component(self.hass, switch.DOMAIN, self.GOOD_CONFIG)
        for ident, port in ports.items():
            if ident != "bad":
                mock_switch.assert_any_call(port)
        assert mock.call(ports["bad"], self.hass) not in mock_switch.mock_calls


class TestMfiSwitch(unittest.TestCase):
    """Test for mFi switch platform."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.port = mock.MagicMock()
        self.switch = mfi.MfiSwitch(self.port)

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_name(self):
        """Test the name."""
        assert self.port.label == self.switch.name

    def test_update(self):
        """Test update."""
        self.switch.update()
        assert self.port.refresh.call_count == 1
        assert self.port.refresh.call_args == mock.call()

    def test_update_with_target_state(self):
        """Test update with target state."""
        self.switch._target_state = True
        self.port.data = {}
        self.port.data["output"] = "stale"
        self.switch.update()
        assert 1.0 == self.port.data["output"]
        assert self.switch._target_state is None
        self.port.data["output"] = "untouched"
        self.switch.update()
        assert "untouched" == self.port.data["output"]

    def test_turn_on(self):
        """Test turn_on."""
        self.switch.turn_on()
        assert self.port.control.call_count == 1
        assert self.port.control.call_args == mock.call(True)
        assert self.switch._target_state

    def test_turn_off(self):
        """Test turn_off."""
        self.switch.turn_off()
        assert self.port.control.call_count == 1
        assert self.port.control.call_args == mock.call(False)
        assert not self.switch._target_state

    def test_current_power_w(self):
        """Test current power."""
        self.port.data = {"active_pwr": 10}
        assert 10 == self.switch.current_power_w

    def test_current_power_w_no_data(self):
        """Test current power if there is no data."""
        self.port.data = {"notpower": 123}
        assert 0 == self.switch.current_power_w

    def test_device_state_attributes(self):
        """Test the state attributes."""
        self.port.data = {"v_rms": 1.25, "i_rms": 2.75}
        assert {"volts": 1.2, "amps": 2.8} == self.switch.device_state_attributes
