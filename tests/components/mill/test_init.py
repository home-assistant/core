"""Tests for Mill init."""

from unittest.mock import patch

from homeassistant.components import mill
from homeassistant.config_entries import ConfigEntryState
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_coro


async def test_setup_with_cloud_config(hass):
    """Test setup of cloud config."""
    entry = MockConfigEntry(
        domain=mill.DOMAIN,
        data={
            mill.CONF_USERNAME: "user",
            mill.CONF_PASSWORD: "pswd",
            mill.CONNECTION_TYPE: mill.CLOUD,
        },
    )
    entry.add_to_hass(hass)
    with patch(
        "mill.Mill.fetch_heater_and_sensor_data", return_value={}
    ) as mock_fetch, patch("mill.Mill.connect", return_value=True) as mock_connect:
        assert await async_setup_component(hass, "mill", entry)
    assert len(mock_fetch.mock_calls) == 1
    assert len(mock_connect.mock_calls) == 1


async def test_setup_with_cloud_config_fails(hass):
    """Test setup of cloud config."""
    entry = MockConfigEntry(
        domain=mill.DOMAIN,
        data={
            mill.CONF_USERNAME: "user",
            mill.CONF_PASSWORD: "pswd",
            mill.CONNECTION_TYPE: mill.CLOUD,
        },
    )
    entry.add_to_hass(hass)
    with patch("mill.Mill.connect", return_value=False):
        assert await async_setup_component(hass, "mill", entry)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_with_old_cloud_config(hass):
    """Test setup of old cloud config."""
    entry = MockConfigEntry(
        domain=mill.DOMAIN,
        data={
            mill.CONF_USERNAME: "user",
            mill.CONF_PASSWORD: "pswd",
        },
    )
    entry.add_to_hass(hass)
    with patch("mill.Mill.fetch_heater_and_sensor_data", return_value={}), patch(
        "mill.Mill.connect", return_value=True
    ) as mock_connect:
        assert await async_setup_component(hass, "mill", entry)

    assert len(mock_connect.mock_calls) == 1


async def test_setup_with_local_config(hass):
    """Test setup of local config."""
    entry = MockConfigEntry(
        domain=mill.DOMAIN,
        data={
            mill.CONF_IP_ADDRESS: "192.168.1.59",
            mill.CONNECTION_TYPE: mill.LOCAL,
        },
    )
    entry.add_to_hass(hass)
    with patch(
        "mill_local.Mill.fetch_heater_and_sensor_data",
        return_value={
            "ambient_temperature": 20,
            "set_temperature": 22,
            "current_power": 0,
        },
    ) as mock_fetch, patch(
        "mill_local.Mill.connect",
        return_value={
            "name": "panel heater gen. 3",
            "version": "0x210927",
            "operation_key": "",
            "status": "ok",
        },
    ) as mock_connect:
        assert await async_setup_component(hass, "mill", entry)

    assert len(mock_fetch.mock_calls) == 1
    assert len(mock_connect.mock_calls) == 1


async def test_unload_entry(hass):
    """Test removing mill client."""
    entry = MockConfigEntry(
        domain=mill.DOMAIN,
        data={
            mill.CONF_USERNAME: "user",
            mill.CONF_PASSWORD: "pswd",
            mill.CONNECTION_TYPE: mill.CLOUD,
        },
    )
    entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=mock_coro(True)
    ) as unload_entry, patch(
        "mill.Mill.fetch_heater_and_sensor_data", return_value={}
    ), patch(
        "mill.Mill.connect", return_value=True
    ):
        assert await async_setup_component(hass, "mill", entry)

        assert await hass.config_entries.async_unload(entry.entry_id)

        assert unload_entry.call_count == 2
        assert entry.entry_id not in hass.data[mill.DOMAIN]
