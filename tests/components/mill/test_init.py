"""Tests for Mill init."""

from unittest.mock import patch

import pytest

from homeassistant.components import mill
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry, mock_coro


async def test_setup_with_cloud_config(hass):
    """Test setup of cloud config."""
    mock_entry = MockConfigEntry(
        domain=mill.DOMAIN,
        data={
            mill.CONF_USERNAME: "user",
            mill.CONF_PASSWORD: "pswd",
            mill.CONNECTION_TYPE: mill.CLOUD,
        },
    )
    mock_entry.add_to_hass(hass)
    with patch("mill.Mill.fetch_heater_and_sensor_data", return_value={}) as mock_fetch:
        with patch("mill.Mill.connect", return_value=True) as mock_connect:
            assert await mill.async_setup_entry(hass, mock_entry)
    assert isinstance(
        hass.data[mill.DOMAIN][mill.CLOUD]["user"].mill_data_connection, mill.Mill
    )
    assert len(mock_fetch.mock_calls) == 1
    assert len(mock_connect.mock_calls) == 1


async def test_setup_with_cloud_config_fails(hass):
    """Test setup of cloud config."""
    mock_entry = MockConfigEntry(
        domain=mill.DOMAIN,
        data={
            mill.CONF_USERNAME: "user",
            mill.CONF_PASSWORD: "pswd",
            mill.CONNECTION_TYPE: mill.CLOUD,
        },
    )
    mock_entry.add_to_hass(hass)
    with patch("mill.Mill.connect", return_value=False):
        with pytest.raises(ConfigEntryNotReady):
            assert not await mill.async_setup_entry(hass, mock_entry)


async def test_setup_with_old_cloud_config(hass):
    """Test setup of old cloud config."""
    mock_entry = MockConfigEntry(
        domain=mill.DOMAIN,
        data={
            mill.CONF_USERNAME: "user",
            mill.CONF_PASSWORD: "pswd",
        },
    )
    mock_entry.add_to_hass(hass)
    with patch("mill.Mill.fetch_heater_and_sensor_data", return_value={}):
        with patch("mill.Mill.connect", return_value=True):
            assert await mill.async_setup_entry(hass, mock_entry)

    assert isinstance(
        hass.data[mill.DOMAIN][mill.CLOUD]["user"].mill_data_connection, mill.Mill
    )


async def test_setup_with_local_config(hass):
    """Test setup of local config."""
    mock_entry = MockConfigEntry(
        domain=mill.DOMAIN,
        data={
            mill.CONF_IP_ADDRESS: "192.168.1.59",
            mill.CONNECTION_TYPE: mill.LOCAL,
        },
    )
    mock_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.mill.climate.async_setup_entry", return_value=None
    ) as mock_setup, patch(
        "mill_local.Mill.fetch_heater_and_sensor_data", return_value={}
    ) as mock_fetch, patch(
        "mill_local.Mill.connect",
        return_value={
            "name": "panel heater gen. 3",
            "version": "0x210927",
            "operation_key": "",
            "status": "ok",
        },
    ) as mock_connect:
        assert await mill.async_setup_entry(hass, mock_entry)
        await hass.async_block_till_done()

    assert isinstance(
        hass.data[mill.DOMAIN][mill.LOCAL][
            mock_entry.data[mill.CONF_IP_ADDRESS]
        ].mill_data_connection,
        mill.MillLocal,
    )
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_fetch.mock_calls) == 1
    assert len(mock_connect.mock_calls) == 1


async def test_unload_entry(hass):
    """Test removing mill client."""
    mock_entry = MockConfigEntry(
        domain=mill.DOMAIN,
        data={
            mill.CONF_USERNAME: "user",
            mill.CONF_PASSWORD: "pswd",
            mill.CONNECTION_TYPE: mill.CLOUD,
        },
    )
    mock_entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=mock_coro(True)
    ) as unload_entry:
        with patch("mill.Mill.connect", return_value=True):
            assert await mill.async_setup_entry(hass, mock_entry)

        assert await mill.async_unload_entry(hass, mock_entry)
        assert unload_entry.call_count == 2
        assert mock_entry.entry_id not in hass.data[mill.DOMAIN]
