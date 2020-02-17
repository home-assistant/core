"""Test Dynalite config flow."""
from asynctest import patch

from homeassistant import config_entries
from homeassistant.components import dynalite


async def run_flow(hass, setup, connection):
    """Run a flow with or without errors and return result."""
    host = "1.2.3.4"
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        return_value=setup,
    ), patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.available", connection
    ), patch(
        "homeassistant.components.dynalite.bridge.CONNECT_INTERVAL", 0
    ):
        result = await hass.config_entries.flow.async_init(
            dynalite.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={dynalite.CONF_HOST: host},
        )
    return result


async def test_flow_works(hass):
    """Test a successful config flow."""
    result = await run_flow(hass, True, True)
    assert result["type"] == "create_entry"


async def test_flow_setup_fails(hass):
    """Test a flow where async_setup fails."""
    result = await run_flow(hass, False, True)
    assert result["type"] == "abort"
    assert result["reason"] == "bridge_setup_failed"


async def test_flow_no_connection(hass):
    """Test a flow where connection times out."""
    result = await run_flow(hass, True, False)
    assert result["type"] == "abort"
    assert result["reason"] == "no_connection"
