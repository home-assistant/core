"""Pytest modules for Aurora ABB Powerone PV inverter sensor integration."""
from homeassistant.components.aurora_abb_powerone.const import (
    ATTR_SERIAL_NUMBER,
    DOMAIN,
)
from homeassistant.const import CONF_ADDRESS, CONF_PORT
from homeassistant.setup import async_setup_component

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_unload_entry(hass):
    """Test unloading the aurora_abb_powerone entry."""

    with patch("aurorapy.client.AuroraSerialClient.connect", return_value=None), patch(
        "homeassistant.components.aurora_abb_powerone.sensor.AuroraSensor.update",
        return_value=None,
    ):
        mock_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_PORT: "/dev/ttyUSB7",
                CONF_ADDRESS: 7,
                ATTR_SERIAL_NUMBER: "876",
            },
        )
        mock_entry.add_to_hass(hass)
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert await hass.config_entries.async_unload(mock_entry.entry_id)
        await hass.async_block_till_done()
