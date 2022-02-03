"""Pytest modules for Aurora ABB Powerone PV inverter sensor integration."""
from unittest.mock import patch

from homeassistant.components.aurora_abb_powerone.const import (
    ATTR_FIRMWARE,
    ATTR_MODEL,
    ATTR_SERIAL_NUMBER,
    DOMAIN,
)
from homeassistant.const import CONF_ADDRESS, CONF_PORT
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_unload_entry(hass):
    """Test unloading the aurora_abb_powerone entry."""

    with patch("aurorapy.client.AuroraSerialClient.connect", return_value=None), patch(
        "homeassistant.components.aurora_abb_powerone.sensor.AuroraSensor.update",
        return_value=None,
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
        mock_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_PORT: "/dev/ttyUSB7",
                CONF_ADDRESS: 7,
                ATTR_MODEL: "model123",
                ATTR_SERIAL_NUMBER: "876",
                ATTR_FIRMWARE: "1.2.3.4",
            },
        )
        mock_entry.add_to_hass(hass)
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert await hass.config_entries.async_unload(mock_entry.entry_id)
        await hass.async_block_till_done()
