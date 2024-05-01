"""The tests for the Vultr sensor platform."""

import pytest
import voluptuous as vol

from homeassistant.components import vultr as base_vultr
import homeassistant.components.vultr.sensor as vultr
from homeassistant.const import (
    CONF_API_KEY,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PLATFORM,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady

CONFIGS = [
    {
        CONF_NAME: "Server {}",
        CONF_API_KEY: "test-api-key",
        CONF_MONITORED_CONDITIONS: vultr.SENSOR_KEYS,
    },
]


@pytest.mark.usefixtures("valid_config")
def test_sensor(hass: HomeAssistant) -> None:
    """Test the Vultr sensor class and methods."""
    hass_devices = []

    def add_entities(devices, action):
        """Mock add devices."""
        for device in devices:
            device.hass = hass
            hass_devices.append(device)

    for config in CONFIGS:
        vultr.setup_platform(hass, config, add_entities, None)

    assert len(hass_devices) == 4

    for device in hass_devices:
        device.update()

        if device.entity_description.key == base_vultr.ATTR_CURRENT_BANDWIDTH_OUT:
            assert device.name == "Server Current Bandwidth Out"
            assert device.icon == "mdi:upload"
            assert device.state == 3.0

        elif device.entity_description.key == base_vultr.ATTR_CURRENT_BANDWIDTH_IN:
            assert device.name == "Server Current Bandwidth In"
            assert device.icon == "mdi:download"
            assert device.state == 2.0

        elif device.entity_description.key == base_vultr.ATTR_PENDING_CHARGES:
            assert device.name == "Server Pending Charges"
            assert device.icon == "mdi:currency-usd"
            assert device.state == 27.64

        elif device.entity_description.key == base_vultr.ATTR_ACCOUNT_BALANCE:
            assert device.name == "Server Account Balance"
            assert device.icon == "mdi:currency-usd"
            assert device.state == 0

        else:
            raise NotImplementedError


def test_invalid_sensor_config() -> None:
    """Test config type failures."""
    with pytest.raises(vol.Invalid):  # No subscription
        vultr.PLATFORM_SCHEMA(
            {
                CONF_PLATFORM: base_vultr.DOMAIN,
                CONF_MONITORED_CONDITIONS: vultr.SENSOR_KEYS,
            }
        )
    with pytest.raises(vol.Invalid):  # Bad monitored_conditions
        vultr.PLATFORM_SCHEMA(
            {
                CONF_PLATFORM: base_vultr.DOMAIN,
                CONF_API_KEY: "123456",
                CONF_MONITORED_CONDITIONS: ["non-existent-condition"],
            }
        )


@pytest.mark.usefixtures("valid_config")
def test_invalid_sensors(hass: HomeAssistant) -> None:
    """Test the VultrSensor fails."""
    hass_devices = []

    def add_entities(devices, action):
        """Mock add devices."""
        for device in devices:
            device.hass = hass
            hass_devices.append(device)

    bad_conf = {
        CONF_NAME: "Vultr {} {}",
        CONF_API_KEY: "",
        CONF_MONITORED_CONDITIONS: vultr.SENSOR_KEYS,
    }  # No subs at all
    with pytest.raises(PlatformNotReady):
        vultr.setup_platform(hass, bad_conf, add_entities, None)
