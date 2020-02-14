"""Test Dynalite __init__."""
from unittest.mock import Mock

from asynctest import patch

from homeassistant.components import dynalite
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_coro


async def test_empty_config(hass):
    """Test with an empty config."""
    assert await async_setup_component(hass, dynalite.DOMAIN, {}) is True
    assert len(hass.config_entries.flow.async_progress()) == 0
    assert hass.data[dynalite.DOMAIN] == {dynalite.DATA_CONFIGS: {}}


async def test_async_setup(hass):
    """Test a successful setup."""
    host = "1.2.3.4"
    port = 789
    with patch.object(
        dynalite.DynaliteBridge, "async_setup", return_value=mock_coro(True)
    ):
        assert (
            await async_setup_component(
                hass,
                dynalite.DOMAIN,
                {
                    dynalite.DOMAIN: {
                        dynalite.CONF_BRIDGES: [
                            {dynalite.CONF_HOST: host, "port": port},
                        ]
                    }
                },
            )
            is True
        )
    assert (
        hass.data[dynalite.DOMAIN][dynalite.DATA_CONFIGS][host][dynalite.CONF_HOST]
        == host
    )
    assert hass.data[dynalite.DOMAIN][dynalite.DATA_CONFIGS][host]["port"] == port


async def test_async_setup_failed(hass):
    """Test a setup when DynaliteBridge.async_setup fails."""
    host = "1.2.3.4"
    port = 789
    with patch.object(
        dynalite.DynaliteBridge, "async_setup", return_value=mock_coro(False)
    ):
        assert (
            await async_setup_component(
                hass,
                dynalite.DOMAIN,
                {
                    dynalite.DOMAIN: {
                        dynalite.CONF_BRIDGES: [
                            {dynalite.CONF_HOST: host, "port": port},
                        ]
                    }
                },
            )
            is True
        )
    assert (
        hass.data[dynalite.DOMAIN][dynalite.DATA_CONFIGS][host][dynalite.CONF_HOST]
        == host
    )
    assert hass.data[dynalite.DOMAIN][dynalite.DATA_CONFIGS][host]["port"] == port


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    host = "1.2.3.4"
    entry = MockConfigEntry(domain=dynalite.DOMAIN, data={"host": host})
    entry.add_to_hass(hass)

    with patch.object(dynalite, "DynaliteBridge") as mock_bridge:
        mock_bridge.return_value.async_setup.return_value = mock_coro(True)
        mock_bridge.return_value.api.config = Mock(bridgeid="aabbccddeeff")
        assert await async_setup_component(hass, dynalite.DOMAIN, {}) is True
    assert len(mock_bridge.return_value.mock_calls) == 1
    assert hass.data[dynalite.DOMAIN].get(entry.entry_id)

    mock_bridge.return_value.async_reset.return_value = mock_coro(True)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert len(mock_bridge.return_value.async_reset.mock_calls) == 1
    assert not hass.data[dynalite.DOMAIN].get(entry.entry_id)
