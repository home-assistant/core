"""Test the init module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


@pytest.mark.asyncio
async def test_async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Test async_setup_entry."""
    with (
        patch(
            "homeassistant.components.daybetter_services.DayBetterApi"
        ) as mock_api_class,
        patch(
            "homeassistant.components.daybetter_services.DayBetterMQTTManager"
        ) as mock_mqtt_class,
        patch(
            "homeassistant.components.daybetter_services.async_setup_services"
        ) as mock_setup_services,
        patch(
            "homeassistant.config_entries.async_forward_entry_setups"
        ) as mock_forward_setups,
    ):
        # Setup mocks
        mock_api = AsyncMock()
        mock_api.fetch_devices = AsyncMock(return_value=[])
        mock_api_class.return_value = mock_api

        mock_mqtt_manager = AsyncMock()
        mock_mqtt_manager.async_connect = AsyncMock(return_value=True)
        mock_mqtt_class.return_value = mock_mqtt_manager

        mock_setup_services.return_value = None
        mock_forward_setups.return_value = None

        # Import and test
        from homeassistant.components.daybetter_services import async_setup_entry

        result = await async_setup_entry(hass, config_entry)

        assert result is True
        assert DOMAIN in hass.data
        assert config_entry.entry_id in hass.data[DOMAIN]

        # Verify API was initialized
        mock_api_class.assert_called_once_with(hass, config_entry.data["token"])

        # Verify MQTT manager was initialized
        mock_mqtt_class.assert_called_once_with(hass, config_entry)

        # Verify services were set up
        mock_setup_services.assert_called_once_with(hass, config_entry)

        # Verify platforms were set up
        mock_forward_setups.assert_called_once()


@pytest.mark.asyncio
async def test_async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Test async_unload_entry."""
    with patch(
        "homeassistant.config_entries.async_unload_platforms"
    ) as mock_unload_platforms:
        # Setup mock
        mock_unload_platforms.return_value = True

        # Setup hass.data
        hass.data[DOMAIN] = {config_entry.entry_id: {}}

        # Import and test
        from homeassistant.components.daybetter_services import async_unload_entry

        result = await async_unload_entry(hass, config_entry)

        assert result is True
        mock_unload_platforms.assert_called_once()

        # Verify data was cleaned up
        assert config_entry.entry_id not in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_trigger_mqtt_connection_service(
    hass: HomeAssistant, config_entry: ConfigEntry
):
    """Test trigger_mqtt_connection service."""
    mock_mqtt_manager = AsyncMock()
    mock_mqtt_manager.async_connect = AsyncMock(return_value=True)

    # Setup hass.data
    hass.data[DOMAIN] = {config_entry.entry_id: {"mqtt_manager": mock_mqtt_manager}}

    # Import and test
    from homeassistant.components.daybetter_services import trigger_mqtt_connection

    service_call = MagicMock()
    await trigger_mqtt_connection(hass, config_entry, service_call)

    mock_mqtt_manager.async_connect.assert_called_once()


@pytest.mark.asyncio
async def test_refresh_devices_service(hass: HomeAssistant, config_entry: ConfigEntry):
    """Test refresh_devices service."""
    mock_api = AsyncMock()
    mock_api.fetch_devices = AsyncMock(return_value=[{"id": "device1"}])

    # Setup hass.data
    hass.data[DOMAIN] = {config_entry.entry_id: {"api": mock_api, "devices": []}}

    # Import and test
    from homeassistant.components.daybetter_services import refresh_devices

    service_call = MagicMock()
    await refresh_devices(hass, config_entry, service_call)

    mock_api.fetch_devices.assert_called_once()
    assert hass.data[DOMAIN][config_entry.entry_id]["devices"] == [{"id": "device1"}]
