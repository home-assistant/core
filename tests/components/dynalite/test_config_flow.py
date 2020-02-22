"""Test Dynalite config flow."""
from itertools import chain, repeat

from asynctest import PropertyMock, patch

from homeassistant import config_entries
from homeassistant.components import dynalite

from tests.common import MockConfigEntry


async def run_flow(hass, setup, connection):
    """Run a flow with or without errors and return result."""
    host = "1.2.3.4"
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        side_effect=setup,
    ), patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.available",
        PropertyMock(side_effect=connection),
    ), patch(
        "homeassistant.components.dynalite.bridge.CONNECT_INTERVAL", 0
    ):
        result = await hass.config_entries.flow.async_init(
            dynalite.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={dynalite.CONF_HOST: host},
        )
        await hass.async_block_till_done()
    return result


async def test_flow_works(hass):
    """Test a successful config flow."""
    result = await run_flow(hass, [True, True], [True, True])
    assert result["type"] == "create_entry"
    assert result["result"].state == "loaded"


async def test_flow_setup_fails(hass):
    """Test a flow where async_setup fails."""
    result = await run_flow(hass, [False], [True])
    assert result["type"] == "abort"
    assert result["reason"] == "bridge_setup_failed"


async def test_flow_no_connection(hass):
    """Test a flow where connection times out."""
    result = await run_flow(hass, [True], repeat(False))
    assert result["type"] == "abort"
    assert result["reason"] == "no_connection"


async def test_flow_setup_fails_in_setup_entry(hass):
    """Test a flow where the initial check works but inside setup_entry, the bridge setup fails."""
    result = await run_flow(hass, [True, False], repeat(True))
    assert result["type"] == "create_entry"
    assert result["result"].state == "setup_error"


async def test_flow_no_connection_in_setup_entry(hass):
    """Test a flow where the initial check works but inside setup_entry, the bridge setup fails."""
    result = await run_flow(hass, [True, True], chain([True], repeat(False)))
    assert result["type"] == "create_entry"
    assert result["result"].state == "setup_retry"


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
