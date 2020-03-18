"""Test Dynalite config flow."""
from asynctest import patch

from homeassistant import config_entries
from homeassistant.components import dynalite

from tests.common import MockConfigEntry


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


async def test_existing(hass):
    """Test when the entry exists with the same config."""
    host = "1.2.3.4"
    MockConfigEntry(
        domain=dynalite.DOMAIN, unique_id=host, data={dynalite.CONF_HOST: host}
    ).add_to_hass(hass)
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        return_value=True,
    ), patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.available", True
    ):
        result = await hass.config_entries.flow.async_init(
            dynalite.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={dynalite.CONF_HOST: host},
        )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_existing_update(hass):
    """Test when the entry exists with the same config."""
    host = "1.2.3.4"
    mock_entry = MockConfigEntry(
        domain=dynalite.DOMAIN, unique_id=host, data={dynalite.CONF_HOST: host}
    )
    mock_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        return_value=True,
    ), patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.available", True
    ):
        result = await hass.config_entries.flow.async_init(
            dynalite.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={dynalite.CONF_HOST: host, "aaa": "bbb"},
        )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert mock_entry.data.get("aaa") == "bbb"
