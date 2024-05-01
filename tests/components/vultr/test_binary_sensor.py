"""Test the Vultr binary sensor platform."""

import pytest
import voluptuous as vol

from homeassistant.components import vultr as base_vultr
from homeassistant.components.vultr import (
    ATTR_ALLOWED_BANDWIDTH,
    ATTR_CREATED_AT,
    ATTR_IPV4_ADDRESS,
    CONF_INSTANCE_ID,
    binary_sensor as vultr,
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


@pytest.mark.usefixtures("valid_config")
def test_binary_sensor(hass: HomeAssistant) -> None:
    """Test successful instance."""
    hass_devices = []

    def add_entities(devices, action):
        """Mock add devices."""
        for device in devices:
            device.hass = hass
            hass_devices.append(device)

    # Setup each of our test configs
    for config in CONFIGS:
        vultr.setup_platform(hass, config, add_entities, None)

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
            assert device.device_class == "power"
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


def test_invalid_sensor_config() -> None:
    """Test config type failures."""
    with pytest.raises(vol.Invalid):  # No subs
        vultr.PLATFORM_SCHEMA({CONF_PLATFORM: base_vultr.DOMAIN})


@pytest.mark.usefixtures("valid_config")
def test_invalid_sensors(hass: HomeAssistant) -> None:
    """Test the VultrBinarySensor fails."""
    hass_devices = []

    def add_entities(devices, action):
        """Mock add devices."""
        for device in devices:
            device.hass = hass
            hass_devices.append(device)

    bad_conf = {}  # No subscription
    with pytest.raises(PlatformNotReady):
        vultr.setup_platform(hass, bad_conf, add_entities, None)

    bad_conf = {
        CONF_NAME: "Missing Server",
        CONF_INSTANCE_ID: "555555",
    }  # Sub not associated with API key (not in server_list)
    with pytest.raises(PlatformNotReady):
        vultr.setup_platform(hass, bad_conf, add_entities, None)
