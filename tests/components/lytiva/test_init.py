"""Tests for Lytiva integration initialization."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.lytiva.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_mqtt_client: MagicMock
) -> None:
    """Test successful setup of a config entry."""
    mock_config_entry.add_to_hass(hass)
    
    with patch("homeassistant.components.lytiva.mqtt_client.Client", return_value=mock_mqtt_client):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    
    assert mock_config_entry.state == ConfigEntryState.LOADED
    assert DOMAIN in hass.data
    assert mock_config_entry.entry_id in hass.data[DOMAIN]
    
    # Verify MQTT client was configured
    mock_mqtt_client.username_pw_set.assert_called_once_with("test_user", "test_pass")
    mock_mqtt_client.connect.assert_called_once()
    mock_mqtt_client.loop_start.assert_called_once()


async def test_setup_entry_connection_failed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_mqtt_client: MagicMock
) -> None:
    """Test setup fails when MQTT connection fails."""
    mock_config_entry.add_to_hass(hass)
    mock_mqtt_client.connect.side_effect = Exception("Connection failed")
    
    with patch("homeassistant.components.lytiva.mqtt_client.Client", return_value=mock_mqtt_client):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    
    assert mock_config_entry.state == ConfigEntryState.SETUP_ERROR


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_mqtt_client: MagicMock
) -> None:
    """Test successful unload of a config entry."""
    mock_config_entry.add_to_hass(hass)
    
    with patch("homeassistant.components.lytiva.mqtt_client.Client", return_value=mock_mqtt_client):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    
    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED
    assert mock_config_entry.entry_id not in hass.data.get(DOMAIN, {})
    
    # Verify MQTT client was properly cleaned up
    mock_mqtt_client.loop_stop.assert_called_once()
    mock_mqtt_client.disconnect.assert_called_once()


async def test_platforms_loaded(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_mqtt_client: MagicMock
) -> None:
    """Test that all platforms are loaded."""
    mock_config_entry.add_to_hass(hass)
    
    with patch("homeassistant.components.lytiva.mqtt_client.Client", return_value=mock_mqtt_client):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    
    # Verify all expected platforms are loaded
    expected_platforms = ["light"]
    
    for platform in expected_platforms:
        assert f"{DOMAIN}.{platform}" in hass.config.components


async def test_mqtt_subscriptions(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_mqtt_client: MagicMock
) -> None:
    """Test that MQTT subscriptions are set up correctly."""
    mock_config_entry.add_to_hass(hass)
    
    with patch("homeassistant.components.lytiva.mqtt_client.Client", return_value=mock_mqtt_client):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Trigger on_connect callback manually to fire subscriptions
        if hasattr(mock_mqtt_client, "on_connect"):
            # signature: client, userdata, flags, rc, *args
            mock_mqtt_client.on_connect(mock_mqtt_client, None, {}, 0)
    
    # Verify discovery and status topics are subscribed
    subscribe_calls = [call[0][0] for call in mock_mqtt_client.subscribe.call_args_list]
    assert "homeassistant/+/+/config" in subscribe_calls
    assert "LYT/+/NODE/E/STATUS" in subscribe_calls
    assert "LYT/+/GROUP/E/STATUS" in subscribe_calls


async def test_discovery_prefix_option(
    hass: HomeAssistant, mock_mqtt_client: MagicMock
) -> None:
    """Test custom discovery prefix from options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Lytiva Test",
        data={
            "broker": "192.168.1.100",
            "port": 1883,
        },
        options={
            "discovery_prefix": "custom_prefix",
        },
        unique_id="lytiva_test",
    )
    entry.add_to_hass(hass)
    
    with patch("homeassistant.components.lytiva.mqtt_client.Client", return_value=mock_mqtt_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Trigger on_connect callback manually
        if hasattr(mock_mqtt_client, "on_connect"):
            mock_mqtt_client.on_connect(mock_mqtt_client, None, {}, 0)
    
    # Verify custom discovery prefix is used
    subscribe_calls = [call[0][0] for call in mock_mqtt_client.subscribe.call_args_list]
    assert "custom_prefix/+/+/config" in subscribe_calls
