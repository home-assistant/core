"""Test the Vultr switch platform."""
import json
import unittest
from unittest.mock import patch

import pytest
import requests_mock
import voluptuous as vol

from homeassistant.components import vultr as base_vultr
from homeassistant.components.vultr import (
    ATTR_ALLOWED_BANDWIDTH,
    ATTR_AUTO_BACKUPS,
    ATTR_COST_PER_MONTH,
    ATTR_CREATED_AT,
    ATTR_IPV4_ADDRESS,
    ATTR_SUBSCRIPTION_ID,
    CONF_SUBSCRIPTION,
    switch as vultr,
)
from homeassistant.const import CONF_NAME, CONF_PLATFORM

from tests.common import get_test_home_assistant, load_fixture
from tests.components.vultr.test_init import VALID_CONFIG


class TestVultrSwitchSetup(unittest.TestCase):
    """Test the Vultr switch platform."""

    DEVICES = []

    def add_entities(self, devices, action):
        """Mock add devices."""
        for device in devices:
            self.DEVICES.append(device)

    def setUp(self):
        """Init values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.configs = [
            {CONF_SUBSCRIPTION: "576965", CONF_NAME: "A Server"},
            {CONF_SUBSCRIPTION: "123456", CONF_NAME: "Failed Server"},
            {CONF_SUBSCRIPTION: "555555", CONF_NAME: vultr.DEFAULT_NAME},
        ]
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Stop our started services."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_switch(self, mock):
        """Test successful instance."""
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

        # Setup each of our test configs
        for config in self.configs:
            vultr.setup_platform(self.hass, config, self.add_entities, None)

        assert len(self.DEVICES) == 3

        tested = 0

        for device in self.DEVICES:
            if device.subscription == "555555":
                assert device.name == "Vultr {}"
                tested += 1

            device.update()
            device_attrs = device.device_state_attributes

            if device.subscription == "555555":
                assert device.name == "Vultr Another Server"
                tested += 1

            if device.name == "A Server":
                assert device.is_on is True
                assert device.state == "on"
                assert device.icon == "mdi:server"
                assert device_attrs[ATTR_ALLOWED_BANDWIDTH] == "1000"
                assert device_attrs[ATTR_AUTO_BACKUPS] == "yes"
                assert device_attrs[ATTR_IPV4_ADDRESS] == "123.123.123.123"
                assert device_attrs[ATTR_COST_PER_MONTH] == "10.05"
                assert device_attrs[ATTR_CREATED_AT] == "2013-12-19 14:45:41"
                assert device_attrs[ATTR_SUBSCRIPTION_ID] == "576965"
                tested += 1

            elif device.name == "Failed Server":
                assert device.is_on is False
                assert device.state == "off"
                assert device.icon == "mdi:server-off"
                assert device_attrs[ATTR_ALLOWED_BANDWIDTH] == "1000"
                assert device_attrs[ATTR_AUTO_BACKUPS] == "no"
                assert device_attrs[ATTR_IPV4_ADDRESS] == "192.168.100.50"
                assert device_attrs[ATTR_COST_PER_MONTH] == "73.25"
                assert device_attrs[ATTR_CREATED_AT] == "2014-10-13 14:45:41"
                assert device_attrs[ATTR_SUBSCRIPTION_ID] == "123456"
                tested += 1

        assert tested == 4

    @requests_mock.Mocker()
    def test_turn_on(self, mock):
        """Test turning a subscription on."""
        with patch(
            "vultr.Vultr.server_list",
            return_value=json.loads(load_fixture("vultr_server_list.json")),
        ), patch("vultr.Vultr.server_start") as mock_start:
            for device in self.DEVICES:
                if device.name == "Failed Server":
                    device.turn_on()

        # Turn on
        assert mock_start.call_count == 1

    @requests_mock.Mocker()
    def test_turn_off(self, mock):
        """Test turning a subscription off."""
        with patch(
            "vultr.Vultr.server_list",
            return_value=json.loads(load_fixture("vultr_server_list.json")),
        ), patch("vultr.Vultr.server_halt") as mock_halt:
            for device in self.DEVICES:
                if device.name == "A Server":
                    device.turn_off()

        # Turn off
        assert mock_halt.call_count == 1

    def test_invalid_switch_config(self):
        """Test config type failures."""
        with pytest.raises(vol.Invalid):  # No subscription
            vultr.PLATFORM_SCHEMA({CONF_PLATFORM: base_vultr.DOMAIN})

    @requests_mock.Mocker()
    def test_invalid_switches(self, mock):
        """Test the VultrSwitch fails."""
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

        bad_conf = {}  # No subscription

        no_subs_setup = vultr.setup_platform(
            self.hass, bad_conf, self.add_entities, None
        )

        assert no_subs_setup is not None

        bad_conf = {
            CONF_NAME: "Missing Server",
            CONF_SUBSCRIPTION: "665544",
        }  # Sub not associated with API key (not in server_list)

        wrong_subs_setup = vultr.setup_platform(
            self.hass, bad_conf, self.add_entities, None
        )

        assert wrong_subs_setup is not None
