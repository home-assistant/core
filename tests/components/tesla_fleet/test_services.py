"""Tests for the Tesla Fleet services."""

from unittest.mock import AsyncMock

import probatio
import pytest

from homeassistant.components.tesla_fleet.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_navigation_gps_request_success(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_tesla_fleet_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful execution of navigation_gps_request service."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "VIN1234567890")},
        name="Tesla Model 3",
    )

    await hass.services.async_call(
        DOMAIN,
        "navigation_gps_request",
        {
            "device_id": device_entry.id,
            "latitude": 37.7749,
            "longitude": -122.4194,
            "order": 1,
        },
        blocking=True,
    )

    mock_tesla_fleet_api.navigation_gps_request.assert_called_once_with(
        vin="VIN1234567890",
        lat=37.7749,
        lon=-122.4194,
        order=1,
    )


async def test_navigation_gps_request_without_optional_order(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_tesla_fleet_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test navigation_gps_request service without optional order parameter."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "VIN1234567890")},
        name="Tesla Model 3",
    )

    await hass.services.async_call(
        DOMAIN,
        "navigation_gps_request",
        {
            "device_id": device_entry.id,
            "latitude": 37.7749,
            "longitude": -122.4194,
        },
        blocking=True,
    )

    mock_tesla_fleet_api.navigation_gps_request.assert_called_once_with(
        vin="VIN1234567890",
        lat=37.7749,
        lon=-122.4194,
        order=None,
    )


async def test_navigation_gps_request_invalid_coordinates(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test navigation_gps_request service with out-of-range coordinates."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "VIN1234567890")},
        name="Tesla Model 3",
    )

    with pytest.raises((probatio.Invalid, ServiceValidationError)):
        await hass.services.async_call(
            DOMAIN,
            "navigation_gps_request",
            {
                "device_id": device_entry.id,
                "latitude": 95.0,  # Invalid latitude (>90)
                "longitude": -122.4194,
            },
            blocking=True,
        )


async def test_navigation_gps_request_api_failure(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_tesla_fleet_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test API exception handling in navigation_gps_request service."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "VIN1234567890")},
        name="Tesla Model 3",
    )

    mock_tesla_fleet_api.navigation_gps_request.side_effect = Exception(
        "Tesla API error"
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "navigation_gps_request",
            {
                "device_id": device_entry.id,
                "latitude": 37.7749,
                "longitude": -122.4194,
            },
            blocking=True,
        )


async def test_navigation_gps_request_device_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test calling service with a non-existent device ID."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "navigation_gps_request",
            {
                "device_id": "non_existent_device_id",
                "latitude": 37.7749,
                "longitude": -122.4194,
            },
            blocking=True,
        )
