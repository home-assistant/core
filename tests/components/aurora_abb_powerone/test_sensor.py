"""Test the Aurora ABB PowerOne Solar PV sensors."""
from unittest.mock import patch

from aurorapy.client import AuroraError, AuroraTimeoutError

from homeassistant.components.aurora_abb_powerone.const import (
    ATTR_DEVICE_NAME,
    ATTR_FIRMWARE,
    ATTR_MODEL,
    ATTR_SERIAL_NUMBER,
    DEFAULT_INTEGRATION_TITLE,
    DOMAIN,
    SCAN_INTERVAL,
)
from homeassistant.const import CONF_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

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
        5: 12345,  # energy
    }
    return returns[index]


def _mock_config_entry():
    return MockConfigEntry(
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
        entry_id="13579",
        unique_id="654321",
    )


async def test_sensors(hass: HomeAssistant) -> None:
    """Test data coming back from inverter."""
    mock_entry = _mock_config_entry()

    with patch("aurorapy.client.AuroraSerialClient.connect", return_value=None), patch(
        "aurorapy.client.AuroraSerialClient.measure",
        side_effect=_simulated_returns,
    ), patch(
        "aurorapy.client.AuroraSerialClient.serial_number",
        return_value="9876543",
    ), patch(
        "aurorapy.client.AuroraSerialClient.version",
        return_value="9.8.7.6",
    ), patch(
        "aurorapy.client.AuroraSerialClient.pn",
        return_value="A.B.C",
    ), patch(
        "aurorapy.client.AuroraSerialClient.firmware",
        return_value="1.234",
    ), patch(
        "aurorapy.client.AuroraSerialClient.cumulated_energy",
        side_effect=_simulated_returns,
    ):
        mock_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        power = hass.states.get("sensor.mydevicename_power")
        assert power
        assert power.state == "45.7"

        temperature = hass.states.get("sensor.mydevicename_temperature")
        assert temperature
        assert temperature.state == "9.9"

        energy = hass.states.get("sensor.mydevicename_energy")
        assert energy
        assert energy.state == "12.35"


async def test_sensor_dark(hass: HomeAssistant) -> None:
    """Test that darkness (no comms) is handled correctly."""
    mock_entry = _mock_config_entry()

    utcnow = dt_util.utcnow()
    # sun is up
    with patch("aurorapy.client.AuroraSerialClient.connect", return_value=None), patch(
        "aurorapy.client.AuroraSerialClient.measure", side_effect=_simulated_returns
    ), patch(
        "aurorapy.client.AuroraSerialClient.cumulated_energy",
        side_effect=_simulated_returns,
    ), patch(
        "aurorapy.client.AuroraSerialClient.serial_number",
        return_value="9876543",
    ), patch(
        "aurorapy.client.AuroraSerialClient.version",
        return_value="9.8.7.6",
    ), patch(
        "aurorapy.client.AuroraSerialClient.pn",
        return_value="A.B.C",
    ), patch(
        "aurorapy.client.AuroraSerialClient.firmware",
        return_value="1.234",
    ):
        mock_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        power = hass.states.get("sensor.mydevicename_power")
        assert power is not None
        assert power.state == "45.7"
    utcnow = dt_util.utcnow()

    # sunset
    with patch("aurorapy.client.AuroraSerialClient.connect", return_value=None), patch(
        "aurorapy.client.AuroraSerialClient.measure",
        side_effect=AuroraTimeoutError("No response after 10 seconds"),
    ), patch(
        "aurorapy.client.AuroraSerialClient.cumulated_energy",
        side_effect=AuroraTimeoutError("No response after 3 tries"),
    ):
        async_fire_time_changed(hass, utcnow + SCAN_INTERVAL * 2)
        await hass.async_block_till_done()
        power = hass.states.get("sensor.mydevicename_power")
        assert power.state == "unknown"
    # sun rose again
    with patch("aurorapy.client.AuroraSerialClient.connect", return_value=None), patch(
        "aurorapy.client.AuroraSerialClient.measure", side_effect=_simulated_returns
    ), patch(
        "aurorapy.client.AuroraSerialClient.cumulated_energy",
        side_effect=_simulated_returns,
    ):
        async_fire_time_changed(hass, utcnow + SCAN_INTERVAL * 4)
        await hass.async_block_till_done()
        power = hass.states.get("sensor.mydevicename_power")
        assert power is not None
        assert power.state == "45.7"
    # sunset
    with patch("aurorapy.client.AuroraSerialClient.connect", return_value=None), patch(
        "aurorapy.client.AuroraSerialClient.measure",
        side_effect=AuroraTimeoutError("No response after 10 seconds"),
    ), patch(
        "aurorapy.client.AuroraSerialClient.cumulated_energy",
        side_effect=AuroraError("No response after 10 seconds"),
    ):
        async_fire_time_changed(hass, utcnow + SCAN_INTERVAL * 6)
        await hass.async_block_till_done()
        power = hass.states.get("sensor.mydevicename_power")
        assert power.state == "unknown"  # should this be 'available'?


async def test_sensor_unknown_error(hass: HomeAssistant) -> None:
    """Test other comms error is handled correctly."""
    mock_entry = _mock_config_entry()

    with patch("aurorapy.client.AuroraSerialClient.connect", return_value=None), patch(
        "aurorapy.client.AuroraSerialClient.measure",
        side_effect=AuroraError("another error"),
    ), patch("serial.Serial.isOpen", return_value=True):
        mock_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        power = hass.states.get("sensor.mydevicename_power_output")
        assert power is None
