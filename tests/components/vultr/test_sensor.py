"""The tests for the Vultr sensor platform."""

import pytest
import voluptuous as vol

from homeassistant.components import vultr as base_vultr
from homeassistant.components.vultr import CONF_SUBSCRIPTION, sensor as vultr
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_PLATFORM,
    UnitOfInformation,
)
from homeassistant.core import HomeAssistant

CONFIGS = [
    {
        CONF_NAME: vultr.DEFAULT_NAME,
        CONF_SUBSCRIPTION: "576965",
        CONF_MONITORED_CONDITIONS: vultr.SENSOR_KEYS,
    },
    {
        CONF_NAME: "Server {}",
        CONF_SUBSCRIPTION: "123456",
        CONF_MONITORED_CONDITIONS: vultr.SENSOR_KEYS,
    },
    {
        CONF_NAME: "VPS Charges",
        CONF_SUBSCRIPTION: "555555",
        CONF_MONITORED_CONDITIONS: ["pending_charges"],
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

    assert len(hass_devices) == 5

    tested = 0

    for device in hass_devices:
        # Test pre update
        if device.subscription == "576965":
            assert device.name == vultr.DEFAULT_NAME

        device.update()

        if (
            device.unit_of_measurement == UnitOfInformation.GIGABYTES
        ):  # Test Bandwidth Used
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
                assert device.state == 3.72
                tested += 1

            elif device.subscription == "555555":  # No {} in name
                assert device.name == "VPS Charges"
                assert device.state == 5.45
                tested += 1

    assert tested == 5


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
                CONF_SUBSCRIPTION: "123456",
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
        CONF_SUBSCRIPTION: "",
        CONF_MONITORED_CONDITIONS: vultr.SENSOR_KEYS,
    }  # No subs at all

    vultr.setup_platform(hass, bad_conf, add_entities, None)

    assert len(hass_devices) == 0
