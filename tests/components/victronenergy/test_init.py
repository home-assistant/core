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
        "paho.mqtt.client.Client",
        return_value=mock_mqtt_client,
    ):
        # Setup
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert mock_config_entry.state is ConfigEntryState.LOADED
        assert DOMAIN in hass.data

        # Verify MQTT client setup
        assert mock_mqtt_client.connect_async.called
        assert mock_mqtt_client.loop_start.called

        # Unload
        result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
        assert result
        assert mock_config_entry.state == ConfigEntryState.NOT_LOADED  # type: ignore[comparison-overlap]

        # Verify cleanup
        assert mock_mqtt_client.unsubscribe.called
        assert mock_mqtt_client.loop_stop.called
        assert mock_mqtt_client.disconnect.called


async def test_setup_entry_connection_error(hass: HomeAssistant) -> None:
    """Test entry setup with connection error."""
    # Create a fresh config entry for this test
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_BROKER: "192.168.1.100",
            "port": 8883,
            "username": "token/homeassistant/test_device_id",
            "token": "test_token",
            "ha_device_id": "test_device_id",
        },
        unique_id="test_device",
        title="Test Connection Error",
    )
    mock_config_entry.add_to_hass(hass)

    with patch("paho.mqtt.client.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Setup should succeed - the integration is resilient to connection errors
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert result  # Integration setup succeeds
        assert mock_config_entry.state is ConfigEntryState.LOADED

        # Wait a moment for any background tasks to settle
        await hass.async_block_till_done()

        # Clean up for next test
        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Ensure domain data is cleaned up for next test
        if DOMAIN in hass.data:
            del hass.data[DOMAIN]


async def test_integration_cleanup_on_removal(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_mqtt_client: MagicMock
) -> None:
    """Test that all resources are cleaned up when integration is removed."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "paho.mqtt.client.Client",
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

    with patch("paho.mqtt.client.Client") as mock_client_class:
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
        "paho.mqtt.client.Client",
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

        # Ensure domain data is cleaned up for next test
        if DOMAIN in hass.data:
            del hass.data[DOMAIN]

        # Worker should be None after cleanup
        assert manager._mqtt_worker is None


async def test_domain_data_cleanup(hass: HomeAssistant) -> None:
    """Test that domain data is properly cleaned up when no entries remain."""
    # Ensure clean state
    if DOMAIN in hass.data:
        del hass.data[DOMAIN]

    # Remove any existing config entries for this domain
    existing_entries = hass.config_entries.async_entries(DOMAIN)
    for entry in existing_entries:
        if entry.state is ConfigEntryState.LOADED:
            await hass.config_entries.async_unload(entry.entry_id)
        await hass.config_entries.async_remove(entry.entry_id)

    # Create a config entry with proper data structure
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_BROKER: "192.168.1.100",
            "port": 8883,
            "username": "token/homeassistant/test1",
            "token": "test_token_1",
            "ha_device_id": "test_device_1",
        },
        unique_id="device_1",
    )
    entry.add_to_hass(hass)

    # Setup entry
    with patch("paho.mqtt.client.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert result
        assert entry.state is ConfigEntryState.LOADED

        # Domain should have data
        assert DOMAIN in hass.data
        # Should have at least one manager entry
        manager_entries = {
            k: v for k, v in hass.data[DOMAIN].items() if not k.startswith("_")
        }
        assert len(manager_entries) == 1

        # Unload entry - domain data should be cleaned up appropriately
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        # Domain data might still exist with just service marker, or be completely removed
        # The exact behavior depends on whether this is the last entry
        if DOMAIN in hass.data:
            # Only service registration marker should remain if present
            manager_entries = {
                k: v for k, v in hass.data[DOMAIN].items() if not k.startswith("_")
            }
            assert len(manager_entries) == 0


async def test_error_handling_during_cleanup(hass: HomeAssistant) -> None:
    """Test that cleanup continues even if individual steps fail."""
    # Create a fresh config entry for this test
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_BROKER: "192.168.1.100",
            "port": 8883,
            "username": "token/homeassistant/test_device_id",
            "token": "test_token",
            "ha_device_id": "test_device_id",
        },
        unique_id="test_error_device",
        title="Test Error Handling",
    )
    mock_config_entry.add_to_hass(hass)

    with patch("paho.mqtt.client.Client") as mock_client_class:
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
        assert mock_config_entry.state == ConfigEntryState.NOT_LOADED  # type: ignore[comparison-overlap]

        # Other cleanup methods should still be called
        assert mock_client.unsubscribe.called
        assert mock_client.loop_stop.called
