"""Test the Victron Energy sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.victronenergy.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_integration_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: MagicMock,
) -> None:
    """Test basic integration setup with sensor platform."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.victronenergy.mqtt_client.Client",
        return_value=mock_mqtt_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify integration is loaded
        assert mock_config_entry.state.name == "LOADED"

        # Verify MQTT manager is created
        assert DOMAIN in hass.data
        assert mock_config_entry.entry_id in hass.data[DOMAIN]


async def test_sensor_platform_registration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: MagicMock,
) -> None:
    """Test that sensor platform gets registered correctly."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.victronenergy.mqtt_client.Client",
        return_value=mock_mqtt_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify sensor platform is loaded
        assert "victronenergy.sensor" in hass.config.components


async def test_mqtt_client_configuration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: MagicMock,
) -> None:
    """Test MQTT client is configured properly."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.victronenergy.mqtt_client.Client",
        return_value=mock_mqtt_client,
    ) as client_mock:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify MQTT client was created
        client_mock.assert_called_once()

        # Verify the manager has the client
        manager = hass.data[DOMAIN][mock_config_entry.entry_id]
        assert manager.client is mock_mqtt_client


async def test_integration_cleanup_on_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: MagicMock,
) -> None:
    """Test integration cleanup when config entry is unloaded."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.victronenergy.mqtt_client.Client",
        return_value=mock_mqtt_client,
    ):
        # Setup
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify setup
        assert DOMAIN in hass.data
        assert mock_config_entry.entry_id in hass.data[DOMAIN]

        # Unload
        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify cleanup
        assert mock_config_entry.entry_id not in hass.data[DOMAIN]


async def test_sensor_mqtt_manager_creation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: MagicMock,
) -> None:
    """Test MQTT manager is created with correct configuration."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.victronenergy.mqtt_client.Client",
        return_value=mock_mqtt_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Get the MQTT manager
        manager = hass.data[DOMAIN][mock_config_entry.entry_id]

        # Verify manager has required attributes
        assert hasattr(manager, "hass")
        assert hasattr(manager, "entry")
        assert hasattr(manager, "client")
        assert manager.hass is hass
        assert manager.entry is mock_config_entry
        assert manager.client is mock_mqtt_client


async def test_device_registry_initialization(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: MagicMock,
) -> None:
    """Test that device registry is initialized correctly."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.victronenergy.mqtt_client.Client",
        return_value=mock_mqtt_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Initially no devices should be registered for this integration
        devices = dr.async_entries_for_config_entry(
            device_registry, mock_config_entry.entry_id
        )
        assert len(devices) == 0

        # But the infrastructure should be in place for device discovery
        manager = hass.data[DOMAIN][mock_config_entry.entry_id]
        assert hasattr(manager, "_device_registry")
