"""Test Dynalite config flow."""

from asynctest import patch

from homeassistant import config_entries
from homeassistant.components import dynalite

from .common import get_bridge_from_hass

from tests.common import MockConfigEntry


async def run_flow(hass, connection):
    """Run a flow with or without errors and return result."""
    host = "1.2.3.4"
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        side_effect=connection,
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
    result = await run_flow(hass, [True, True])
    assert result["type"] == "create_entry"
    assert result["result"].state == "loaded"


async def test_flow_setup_fails(hass):
    """Test a flow where async_setup fails."""
    result = await run_flow(hass, [False])
    assert result["type"] == "abort"
    assert result["reason"] == "no_connection"


async def test_flow_setup_fails_in_setup_entry(hass):
    """Test a flow where the initial check works but inside setup_entry, the bridge setup fails."""
    result = await run_flow(hass, [True, False])
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
    ):
        result = await hass.config_entries.flow.async_init(
            dynalite.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={dynalite.CONF_HOST: host},
        )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_existing_update(hass):
    """Test when the entry exists with a different config."""
    host = "1.2.3.4"
    port1 = 7777
    port2 = 8888
    with patch(
        "homeassistant.components.dynalite.bridge.DynaliteDevices.async_setup",
        return_value=True,
    ):
        assert await hass.config_entries.flow.async_init(
            dynalite.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={dynalite.CONF_HOST: host, dynalite.CONF_PORT: port1},
        )
        await hass.async_block_till_done()
        old_bridge = get_bridge_from_hass(hass)
        assert old_bridge.dynalite_devices.port == port1
        result = await hass.config_entries.flow.async_init(
            dynalite.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={dynalite.CONF_HOST: host, dynalite.CONF_PORT: port2},
        )
        await hass.async_block_till_done()
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    bridge = get_bridge_from_hass(hass)
    assert bridge.dynalite_devices.port == port2
