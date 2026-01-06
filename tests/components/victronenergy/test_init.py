"""Test the Victron Energy integration initialization and cleanup."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.components.victronenergy.const import CONF_BROKER, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_unload_and_reload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_mqtt_client: MagicMock
) -> None:
    """Test entry setup and unload."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.victronenergy.mqtt_client.Client",
        return_value=mock_mqtt_client,
    ):
        # Setup
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert mock_config_entry.state is ConfigEntryState.LOADED
        assert DOMAIN in hass.data

        # Verify MQTT client setup
        assert mock_mqtt_client.connect.called
        assert mock_mqtt_client.loop_start.called

        # Unload
        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

        # Verify cleanup
        assert mock_mqtt_client.unsubscribe.called
        assert mock_mqtt_client.loop_stop.called
        assert mock_mqtt_client.disconnect.called


async def test_setup_entry_connection_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test entry setup with connection error."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.victronenergy.mqtt_client.Client"
    ) as mock_client_class:
        mock_client = MagicMock()
        mock_client.connect.side_effect = ConnectionError("Cannot connect")
        mock_client_class.return_value = mock_client

        # Setup should fail
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert not result
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_integration_cleanup_on_removal(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_mqtt_client: MagicMock
) -> None:
    """Test that all resources are cleaned up when integration is removed."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.victronenergy.mqtt_client.Client",
        return_value=mock_mqtt_client,
    ):
        # Setup
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert mock_config_entry.state is ConfigEntryState.LOADED

        # Verify manager is created
        assert DOMAIN in hass.data
        assert mock_config_entry.entry_id in hass.data[DOMAIN]

        # Remove entry completely
        await hass.config_entries.async_remove(mock_config_entry.entry_id)

        # Verify complete cleanup
        assert mock_mqtt_client.unsubscribe.called
        assert mock_mqtt_client.loop_stop.called
        assert mock_mqtt_client.disconnect.called

        # Verify MQTT callbacks are cleared
        assert mock_mqtt_client.on_connect is None
        assert mock_mqtt_client.on_message is None
        assert mock_mqtt_client.on_disconnect is None


async def test_mqtt_connection_callbacks(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test MQTT connection callback handling."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.victronenergy.mqtt_client.Client"
    ) as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        await hass.config_entries.async_setup(mock_config_entry.entry_id)

        # Verify callbacks are set
        assert mock_client.on_connect is not None
        assert mock_client.on_message is not None
        assert mock_client.on_disconnect is not None

        # Test successful connection callback
        mock_client.on_connect(mock_client, None, None, 0)

        # Test message callback
        mock_msg = MagicMock()
        mock_msg.topic = "N/test/system/0/Ac/Grid/L1/Power"
        mock_msg.payload = b'{"value": 1250.5}'
        mock_client.on_message(mock_client, None, mock_msg)


async def test_mqtt_worker_cleanup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_mqtt_client: MagicMock
) -> None:
    """Test MQTT worker proper cleanup."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.victronenergy.mqtt_client.Client",
        return_value=mock_mqtt_client,
    ):
        # Setup
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

        # Get the manager
        manager = hass.data[DOMAIN][mock_config_entry.entry_id]

        # Verify worker is created
        assert manager._mqtt_worker is not None

        # Test cleanup
        await hass.config_entries.async_unload(mock_config_entry.entry_id)

        # Worker should be None after cleanup
        assert manager._mqtt_worker is None


async def test_domain_data_cleanup(hass: HomeAssistant) -> None:
    """Test that domain data is properly cleaned up when no entries remain."""
    # Create two config entries
    entry1 = MockConfigEntry(domain=DOMAIN, data={CONF_BROKER: "192.168.1.100"})
    entry2 = MockConfigEntry(domain=DOMAIN, data={CONF_BROKER: "192.168.1.101"})

    entry1.add_to_hass(hass)
    entry2.add_to_hass(hass)

    with patch("homeassistant.components.victronenergy.mqtt_client.Client"):
        # Setup both entries
        await hass.config_entries.async_setup(entry1.entry_id)
        await hass.config_entries.async_setup(entry2.entry_id)

        # Domain should have data
        assert DOMAIN in hass.data
        assert len(hass.data[DOMAIN]) == 2

        # Unload first entry - domain data should remain
        await hass.config_entries.async_unload(entry1.entry_id)
        assert DOMAIN in hass.data
        assert len(hass.data[DOMAIN]) == 1

        # Unload second entry - domain data should be cleaned up
        await hass.config_entries.async_unload(entry2.entry_id)
        assert DOMAIN not in hass.data


async def test_error_handling_during_cleanup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that cleanup continues even if individual steps fail."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.victronenergy.mqtt_client.Client"
    ) as mock_client_class:
        mock_client = MagicMock()
        # Make disconnect raise an exception
        mock_client.disconnect.side_effect = Exception("Disconnect failed")
        mock_client_class.return_value = mock_client

        # Setup should succeed
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert mock_config_entry.state is ConfigEntryState.LOADED

        # Unload should succeed even with disconnect error
        result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
        assert result
        assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

        # Other cleanup methods should still be called
        assert mock_client.unsubscribe.called
        assert mock_client.loop_stop.called
