"""Test the Aurora ABB PowerOne Solar PV sensors."""
from unittest.mock import patch

from homeassistant.components.aurora_abb_powerone.const import (
    ATTR_DEVICE_NAME,
    ATTR_FIRMWARE,
    ATTR_MODEL,
    ATTR_SERIAL_NUMBER,
    DEFAULT_INTEGRATION_TITLE,
    DOMAIN,
)
from homeassistant.const import CONF_ADDRESS, CONF_PORT
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, assert_setup_component

# from tcp test_sensor.py
# async def test_setup_platform_valid_config(hass, mock_socket):
#     """Check a valid configuration and call add_entities with sensor."""
#     with assert_setup_component(1, "sensor"):
#         assert await async_setup_component(hass, "sensor", TEST_CONFIG)
#         await hass.async_block_till_done()

TEST_CONFIG = {
    "sensor": {
        "platform": "aurora_abb_powerone",
        "device": "/dev/fakedevice0",
        "address": 2,
    }
}


def _simulated_returns(index, global_measure=None):
    returns = {
        3: 45.678,  # power
        21: 9.876,  # temperature
    }
    return returns[index]


async def test_setup_platform_valid_config(hass):
    """Test that (deprecated) yaml import still works."""
    with patch("aurorapy.client.AuroraSerialClient.connect", return_value=None), patch(
        "aurorapy.client.AuroraSerialClient.measure",
        side_effect=_simulated_returns,
    ), assert_setup_component(1, "sensor"):
        assert await async_setup_component(hass, "sensor", TEST_CONFIG)
        await hass.async_block_till_done()
    power = hass.states.get("sensor.power_output")
    assert power
    assert power.state == "45.7"


async def test_sensors(hass):
    """Test data coming back from inverter."""
    mock_entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title=DEFAULT_INTEGRATION_TITLE,
        data={
            CONF_PORT: "/dev/usb999",
            CONF_ADDRESS: 3,
            ATTR_DEVICE_NAME: "mydevicename",
            ATTR_MODEL: "mymodel",
            ATTR_SERIAL_NUMBER: "123456",
            ATTR_FIRMWARE: "1.2.3.4",
        },
        source="dummysource",
        system_options={},
        entry_id="13579",
    )

    with patch("aurorapy.client.AuroraSerialClient.connect", return_value=None), patch(
        "aurorapy.client.AuroraSerialClient.measure",
        side_effect=_simulated_returns,
    ):
        mock_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        power = hass.states.get("sensor.power_output")
        assert power
        assert power.state == "45.7"

        temperature = hass.states.get("sensor.temperature")
        assert temperature
        assert temperature.state == "9.9"
