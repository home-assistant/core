"""The tests for the WSDOT platform."""
from datetime import datetime, timedelta, timezone
import re
import unittest

import requests_mock

import homeassistant.components.wsdot.sensor as wsdot
from homeassistant.components.wsdot.sensor import (
    ATTR_DESCRIPTION,
    ATTR_TIME_UPDATED,
    CONF_API_KEY,
    CONF_ID,
    CONF_NAME,
    CONF_TRAVEL_TIMES,
    RESOURCE,
    SCAN_INTERVAL,
)
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant, load_fixture


class TestWSDOT(unittest.TestCase):
    """Test the WSDOT platform."""

    def add_entities(self, new_entities, update_before_add=False):
        """Mock add entities."""
        if update_before_add:
            for entity in new_entities:
                entity.update()

        for entity in new_entities:
            self.entities.append(entity)

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.config = {
            CONF_API_KEY: "foo",
            SCAN_INTERVAL: timedelta(seconds=120),
            CONF_TRAVEL_TIMES: [{CONF_ID: 96, CONF_NAME: "I90 EB"}],
        }
        self.entities = []
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_with_config(self):
        """Test the platform setup with configuration."""
        assert setup_component(self.hass, "sensor", {"wsdot": self.config})

    @requests_mock.Mocker()
    def test_setup(self, mock_req):
        """Test for operational WSDOT sensor with proper attributes."""
        uri = re.compile(RESOURCE + "*")
        mock_req.get(uri, text=load_fixture("wsdot.json"))
        wsdot.setup_platform(self.hass, self.config, self.add_entities)
        assert len(self.entities) == 1
        sensor = self.entities[0]
        assert sensor.name == "I90 EB"
        assert sensor.state == 11
        assert (
            sensor.device_state_attributes[ATTR_DESCRIPTION]
            == "Downtown Seattle to Downtown Bellevue via I-90"
        )
        assert sensor.device_state_attributes[ATTR_TIME_UPDATED] == datetime(
            2017, 1, 21, 15, 10, tzinfo=timezone(timedelta(hours=-8))
        )
