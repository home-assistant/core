"""The tests for the DTE Energy Bridge."""

import unittest

import requests_mock

from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant

DTE_ENERGY_BRIDGE_CONFIG = {"platform": "dte_energy_bridge", "ip": "192.168.1.1"}


class TestDteEnergyBridgeSetup(unittest.TestCase):
    """Test the DTE Energy Bridge platform."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.addCleanup(self.hass.stop)

    def test_setup_with_config(self):
        """Test the platform setup with configuration."""
        assert setup_component(
            self.hass, "sensor", {"dte_energy_bridge": DTE_ENERGY_BRIDGE_CONFIG}
        )

    @requests_mock.Mocker()
    def test_setup_correct_reading(self, mock_req):
        """Test DTE Energy bridge returns a correct value."""
        mock_req.get(
            "http://{}/instantaneousdemand".format(DTE_ENERGY_BRIDGE_CONFIG["ip"]),
            text=".411 kW",
        )
        assert setup_component(
            self.hass, "sensor", {"sensor": DTE_ENERGY_BRIDGE_CONFIG}
        )
        self.hass.block_till_done()
        assert "0.411" == self.hass.states.get("sensor.current_energy_usage").state

    @requests_mock.Mocker()
    def test_setup_incorrect_units_reading(self, mock_req):
        """Test DTE Energy bridge handles a value with incorrect units."""
        mock_req.get(
            "http://{}/instantaneousdemand".format(DTE_ENERGY_BRIDGE_CONFIG["ip"]),
            text="411 kW",
        )
        assert setup_component(
            self.hass, "sensor", {"sensor": DTE_ENERGY_BRIDGE_CONFIG}
        )
        self.hass.block_till_done()
        assert "0.411" == self.hass.states.get("sensor.current_energy_usage").state

    @requests_mock.Mocker()
    def test_setup_bad_format_reading(self, mock_req):
        """Test DTE Energy bridge handles an invalid value."""
        mock_req.get(
            "http://{}/instantaneousdemand".format(DTE_ENERGY_BRIDGE_CONFIG["ip"]),
            text="411",
        )
        assert setup_component(
            self.hass, "sensor", {"sensor": DTE_ENERGY_BRIDGE_CONFIG}
        )
        self.hass.block_till_done()
        assert "unknown" == self.hass.states.get("sensor.current_energy_usage").state
