"""Test the Vultr switch platform."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.components import vultr as base_vultr
from homeassistant.components.vultr import (
    ATTR_ALLOWED_BANDWIDTH,
    ATTR_CREATED_AT,
    ATTR_IPV4_ADDRESS,
    CONF_INSTANCE_ID,
    switch as vultr,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady

CONFIGS = [
    {
        CONF_API_KEY: "123",
        CONF_INSTANCE_ID: "db731ada-1326-4186-85dc-c88b899c6639",
        CONF_NAME: "A Server",
    },
    {
        CONF_API_KEY: "123",
        CONF_INSTANCE_ID: "db731ada-1326-4186-85dc-c88b899c6640",
        CONF_NAME: "Stopped Server",
    },
    {
        CONF_API_KEY: "123",
        CONF_INSTANCE_ID: "db731ada-1326-4186-85dc-c88b899c6641",
        CONF_NAME: vultr.DEFAULT_NAME,
    },
]


@pytest.fixture(name="hass_devices")
def load_hass_devices(hass: HomeAssistant):
    """Load a valid config."""
    hass_devices = []

    def add_entities(devices, action):
        """Mock add devices."""
        for device in devices:
            device.hass = hass
            hass_devices.append(device)

    # Setup each of our test configs
    for config in CONFIGS:
        vultr.setup_platform(hass, config, add_entities, None)

    return hass_devices


@pytest.mark.usefixtures("valid_config")
def test_switch(hass: HomeAssistant, hass_devices: list[vultr.VultrSwitch]):
    """Test successful instance."""

    assert len(hass_devices) == 3

    for index, device in enumerate(hass_devices):
        # Test pre data retrieval
        assert device.name == CONFIGS[index][CONF_NAME]

        device.update()
        device_attrs = device.extra_state_attributes

        if device.instance_id == CONFIGS[2][CONF_INSTANCE_ID]:
            assert device.name == "Vultr Another Server"

        if device.instance_id == CONFIGS[0][CONF_INSTANCE_ID]:
            assert device.is_on is True
            assert device.state == "on"
            assert device.icon == "mdi:server"
            assert device_attrs[ATTR_ALLOWED_BANDWIDTH] == 1000
            assert device_attrs[ATTR_IPV4_ADDRESS] == "45.77.107.183"
            assert device_attrs[ATTR_CREATED_AT] == "2020-09-18T20:30:45+00:00"

        elif device.instance_id == CONFIGS[1][CONF_INSTANCE_ID]:
            assert device.is_on is False
            assert device.state == "off"
            assert device.icon == "mdi:server-off"
            assert device_attrs[ATTR_ALLOWED_BANDWIDTH] == 2000
            assert device_attrs[ATTR_IPV4_ADDRESS] == "45.77.107.184"
            assert device_attrs[ATTR_CREATED_AT] == "2020-09-18T20:57:45+00:00"


@pytest.mark.usefixtures("valid_config")
def test_turn_on(hass: HomeAssistant, hass_devices: list[vultr.VultrSwitch]):
    """Test turning an instance on."""
    with patch("homeassistant.components.vultr.Vultr.start") as mock_start:
        for device in hass_devices:
            if device.instance_id == CONFIGS[1][CONF_INSTANCE_ID]:
                device.update()
                device.turn_on()

    # Turn on
    assert mock_start.call_count == 1


@pytest.mark.usefixtures("valid_config")
def test_turn_off(hass: HomeAssistant, hass_devices: list[vultr.VultrSwitch]):
    """Test turning an instance off."""
    with patch("homeassistant.components.vultr.Vultr.halt") as mock_halt:
        for device in hass_devices:
            if device.instance_id == CONFIGS[0][CONF_INSTANCE_ID]:
                device.update()
                device.turn_off()

    # Turn off
    assert mock_halt.call_count == 1


def test_invalid_switch_config() -> None:
    """Test config type failures."""
    with pytest.raises(vol.Invalid):  # No subscription
        vultr.PLATFORM_SCHEMA({CONF_PLATFORM: base_vultr.DOMAIN})


@pytest.mark.usefixtures("valid_config")
def test_invalid_switches(hass: HomeAssistant) -> None:
    """Test the VultrSwitch fails."""
    hass_devices = []

    def add_entities(devices, action):
        """Mock add devices."""
        hass_devices.extend(devices)

    bad_conf = {}  # No subscription
    with pytest.raises(PlatformNotReady):
        vultr.setup_platform(hass, bad_conf, add_entities, None)

    bad_conf = {
        CONF_NAME: "Missing Server",
        CONF_INSTANCE_ID: "665544",
    }  # Sub not associated with API key (not in server_list)
    with pytest.raises(PlatformNotReady):
        vultr.setup_platform(hass, bad_conf, add_entities, None)
