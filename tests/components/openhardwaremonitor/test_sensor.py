"""The tests for the Open Hardware Monitor platform."""
import unittest

import requests_mock

from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant, load_fixture


class TestOpenHardwareMonitorSetup(unittest.TestCase):
    """Test the Open Hardware Monitor platform."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.config = {
            "sensor": {
                "platform": "openhardwaremonitor",
                "host": "localhost",
                "port": 8085,
            }
        }
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Stop everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_setup(self, mock_req):
        """Test for successfully setting up the platform."""
        mock_req.get(
            "http://localhost:8085/data.json",
            text=load_fixture("openhardwaremonitor.json"),
        )

        assert setup_component(self.hass, "sensor", self.config)
        self.hass.block_till_done()
        entities = self.hass.states.async_entity_ids("sensor")
        assert len(entities) == 38

        state = self.hass.states.get(
            "sensor.test_pc_intel_core_i7_7700_clocks_bus_speed"
        )

        assert state is not None
        assert state.state == "100"
