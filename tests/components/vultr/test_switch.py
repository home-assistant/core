"""Test the Vultr switch platform."""
import json
from unittest.mock import patch

import pytest
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
from homeassistant.core import HomeAssistant

from .test_init import VALID_CONFIG

from tests.common import load_fixture

CONFIGS = [
    {CONF_SUBSCRIPTION: "576965", CONF_NAME: "A Server"},
    {CONF_SUBSCRIPTION: "123456", CONF_NAME: "Failed Server"},
    {CONF_SUBSCRIPTION: "555555", CONF_NAME: vultr.DEFAULT_NAME},
]


def test_switch(hass: HomeAssistant, requests_mock):
    """Test successful instance."""
    hass_devices = []

    def add_entities(devices, action):
        """Mock add devices."""
        for device in devices:
            device.hass = hass
            hass_devices.append(device)

    requests_mock.get(
        "https://api.vultr.com/v1/account/info?api_key=ABCDEFG1234567",
        text=load_fixture("account_info.json", "vultr"),
    )

    with patch(
        "vultr.Vultr.server_list",
        return_value=json.loads(load_fixture("server_list.json", "vultr")),
    ):
        # Setup hub
        base_vultr.setup(hass, VALID_CONFIG)

    # Setup each of our test configs
    for config in CONFIGS:
        vultr.setup_platform(hass, config, add_entities, None)

    assert len(hass_devices) == 3

    tested = 0

    for device in hass_devices:
        if device.subscription == "555555":
            assert device.name == "Vultr {}"
            tested += 1

        device.update()
        device_attrs = device.extra_state_attributes

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


def test_turn_on(requests_mock):
    """Test turning a subscription on."""
    hass_devices = []

    def add_entities(devices, action):
        """Mock add devices."""
        for device in devices:
            hass_devices.append(device)

    with patch(
        "vultr.Vultr.server_list",
        return_value=json.loads(load_fixture("server_list.json", "vultr")),
    ), patch("vultr.Vultr.server_start") as mock_start:
        for device in hass_devices:
            if device.name == "Failed Server":
                device.turn_on()

    # Turn on
    assert mock_start.call_count == 1


def test_turn_off(requests_mock):
    """Test turning a subscription off."""
    hass_devices = []

    def add_entities(devices, action):
        """Mock add devices."""
        for device in devices:
            hass_devices.append(device)

    with patch(
        "vultr.Vultr.server_list",
        return_value=json.loads(load_fixture("server_list.json", "vultr")),
    ), patch("vultr.Vultr.server_halt") as mock_halt:
        for device in hass_devices:
            if device.name == "A Server":
                device.turn_off()

    # Turn off
    assert mock_halt.call_count == 1


def test_invalid_switch_config():
    """Test config type failures."""
    with pytest.raises(vol.Invalid):  # No subscription
        vultr.PLATFORM_SCHEMA({CONF_PLATFORM: base_vultr.DOMAIN})


def test_invalid_switches(hass: HomeAssistant, requests_mock):
    """Test the VultrSwitch fails."""
    hass_devices = []

    def add_entities(devices, action):
        """Mock add devices."""
        for device in devices:
            hass_devices.append(device)

    requests_mock.get(
        "https://api.vultr.com/v1/account/info?api_key=ABCDEFG1234567",
        text=load_fixture("account_info.json", "vultr"),
    )

    with patch(
        "vultr.Vultr.server_list",
        return_value=json.loads(load_fixture("server_list.json", "vultr")),
    ):
        # Setup hub
        base_vultr.setup(hass, VALID_CONFIG)

    bad_conf = {}  # No subscription

    no_subs_setup = vultr.setup_platform(hass, bad_conf, add_entities, None)

    assert no_subs_setup is not None

    bad_conf = {
        CONF_NAME: "Missing Server",
        CONF_SUBSCRIPTION: "665544",
    }  # Sub not associated with API key (not in server_list)

    wrong_subs_setup = vultr.setup_platform(hass, bad_conf, add_entities, None)

    assert wrong_subs_setup is not None
