"""The tests for the Vultr sensor platform."""
import json
import unittest
from unittest.mock import patch

import pytest
import requests_mock
import voluptuous as vol

from homeassistant.components import vultr as base_vultr
from homeassistant.components.vultr import CONF_SUBSCRIPTION
import homeassistant.components.vultr.sensor as vultr
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PLATFORM,
    DATA_GIGABYTES,
)

from tests.common import get_test_home_assistant, load_fixture
from tests.components.vultr.test_init import VALID_CONFIG


class TestVultrSensorSetup(unittest.TestCase):
    """Test the Vultr platform."""

    DEVICES = []

    def add_entities(self, devices, action):
        """Mock add devices."""
        for device in devices:
            self.DEVICES.append(device)

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.configs = [
            {
                CONF_NAME: vultr.DEFAULT_NAME,
                CONF_SUBSCRIPTION: "576965",
                CONF_MONITORED_CONDITIONS: vultr.MONITORED_CONDITIONS,
            },
            {
                CONF_NAME: "Server {}",
                CONF_SUBSCRIPTION: "123456",
                CONF_MONITORED_CONDITIONS: vultr.MONITORED_CONDITIONS,
            },
            {
                CONF_NAME: "VPS Charges",
                CONF_SUBSCRIPTION: "555555",
                CONF_MONITORED_CONDITIONS: ["pending_charges"],
            },
        ]
        self.addCleanup(self.hass.stop)

    @requests_mock.Mocker()
    def test_sensor(self, mock):
        """Test the Vultr sensor class and methods."""
        mock.get(
            "https://api.vultr.com/v1/account/info?api_key=ABCDEFG1234567",
            text=load_fixture("vultr_account_info.json"),
        )

        with patch(
            "vultr.Vultr.server_list",
            return_value=json.loads(load_fixture("vultr_server_list.json")),
        ):
            # Setup hub
            base_vultr.setup(self.hass, VALID_CONFIG)

        for config in self.configs:
            setup = vultr.setup_platform(self.hass, config, self.add_entities, None)

            assert setup is None

        assert len(self.DEVICES) == 5

        tested = 0

        for device in self.DEVICES:

            # Test pre update
            if device.subscription == "576965":
                assert vultr.DEFAULT_NAME == device.name

            device.update()

            if device.unit_of_measurement == DATA_GIGABYTES:  # Test Bandwidth Used
                if device.subscription == "576965":
                    assert device.name == "Vultr my new server Current Bandwidth Used"
                    assert device.icon == "mdi:chart-histogram"
                    assert device.state == 131.51
                    assert device.icon == "mdi:chart-histogram"
                    tested += 1

                elif device.subscription == "123456":
                    assert device.name == "Server Current Bandwidth Used"
                    assert device.state == 957.46
                    tested += 1

            elif device.unit_of_measurement == "US$":  # Test Pending Charges

                if device.subscription == "576965":  # Default 'Vultr {} {}'
                    assert device.name == "Vultr my new server Pending Charges"
                    assert device.icon == "mdi:currency-usd"
                    assert device.state == 46.67
                    assert device.icon == "mdi:currency-usd"
                    tested += 1

                elif device.subscription == "123456":  # Custom name with 1 {}
                    assert device.name == "Server Pending Charges"
                    assert device.state == "not a number"
                    tested += 1

                elif device.subscription == "555555":  # No {} in name
                    assert device.name == "VPS Charges"
                    assert device.state == 5.45
                    tested += 1

        assert tested == 5

    def test_invalid_sensor_config(self):
        """Test config type failures."""
        with pytest.raises(vol.Invalid):  # No subscription
            vultr.PLATFORM_SCHEMA(
                {
                    CONF_PLATFORM: base_vultr.DOMAIN,
                    CONF_MONITORED_CONDITIONS: vultr.MONITORED_CONDITIONS,
                }
            )
        with pytest.raises(vol.Invalid):  # Bad monitored_conditions
            vultr.PLATFORM_SCHEMA(
                {
                    CONF_PLATFORM: base_vultr.DOMAIN,
                    CONF_SUBSCRIPTION: "123456",
                    CONF_MONITORED_CONDITIONS: ["non-existent-condition"],
                }
            )

    @requests_mock.Mocker()
    def test_invalid_sensors(self, mock):
        """Test the VultrSensor fails."""
        mock.get(
            "https://api.vultr.com/v1/account/info?api_key=ABCDEFG1234567",
            text=load_fixture("vultr_account_info.json"),
        )

        with patch(
            "vultr.Vultr.server_list",
            return_value=json.loads(load_fixture("vultr_server_list.json")),
        ):
            # Setup hub
            base_vultr.setup(self.hass, VALID_CONFIG)

        bad_conf = {
            CONF_MONITORED_CONDITIONS: vultr.MONITORED_CONDITIONS
        }  # No subs at all

        no_sub_setup = vultr.setup_platform(
            self.hass, bad_conf, self.add_entities, None
        )

        assert no_sub_setup is None
        assert len(self.DEVICES) == 0
