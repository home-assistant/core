"""Tests for the Kermi config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.kermi.config_flow import KermiConfigFlow
from homeassistant.components.kermi.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry


async def test_show_form(hass: config_entries.HomeAssistant, flow: KermiConfigFlow):
    """Test that the form is served with no input."""
    result = await flow.async_step_user()
    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_create_entry(hass: config_entries.HomeAssistant, flow: KermiConfigFlow):
    """Test that the user step works."""
    test_data = {
        CONF_HOST: "test_host",
        "heatpump_device_address": 40,
        "climate_device_address": 50,
        "water_heater_device_address": 51,
    }
    with patch(
        "homeassistant.components.kermi.async_setup_entry",
        return_value=True,
    ):
        result = await flow.async_step_user(test_data)
    assert result["type"] == "create_entry"
    assert result["title"] == test_data[CONF_HOST]
    assert result["data"] == test_data


async def test_setup_entry(hass: config_entries.HomeAssistant, flow: KermiConfigFlow):
    """Test that the entry is setup."""
    test_entry = MockConfigEntry(
        domain=DOMAIN,
        title="test",
        data={"host": "test_host"},
        source="test",
    )
    test_entry.connection_class = config_entries.CONN_CLASS_LOCAL_POLL
    test_entry.add_to_hass(hass)
