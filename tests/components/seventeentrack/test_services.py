"""Tests for the seventeentrack service."""

from unittest.mock import AsyncMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.seventeentrack import DOMAIN, SERVICE_GET_PACKAGES
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from . import init_integration
from .conftest import get_package

from tests.common import MockConfigEntry


async def test_get_packages_from_list(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Ensure service returns only the packages in the list."""
    await _mock_packages(mock_seventeentrack)
    await init_integration(hass, mock_config_entry)
    service_response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PACKAGES,
        {
            "config_entry_id": mock_config_entry.entry_id,
            "package_state": ["in_transit", "delivered"],
        },
        blocking=True,
        return_response=True,
    )

    assert service_response == snapshot


async def test_get_all_packages(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Ensure service returns all packages when non provided."""
    await _mock_packages(mock_seventeentrack)
    await init_integration(hass, mock_config_entry)
    service_response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PACKAGES,
        {
            "config_entry_id": mock_config_entry.entry_id,
        },
        blocking=True,
        return_response=True,
    )

    assert service_response == snapshot


async def test_service_called_with_unloaded_entry(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test service call with not ready config entry."""
    await init_integration(hass, mock_config_entry)
    mock_config_entry.mock_state(hass, ConfigEntryState.SETUP_ERROR)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_PACKAGES,
            {
                "config_entry_id": mock_config_entry.entry_id,
            },
            blocking=True,
            return_response=True,
        )


async def test_service_called_with_non_17track_device(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test service calls with non 17Track device."""
    await init_integration(hass, mock_config_entry)

    other_domain = "Not17Track"
    other_config_id = "555"
    other_mock_config_entry = MockConfigEntry(
        title="Not 17Track", domain=other_domain, entry_id=other_config_id
    )
    other_mock_config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=other_config_id,
        identifiers={(other_domain, "1")},
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_PACKAGES,
            {
                "config_entry_id": device_entry.id,
            },
            blocking=True,
            return_response=True,
        )


async def _mock_packages(mock_seventeentrack):
    package1 = get_package(status=10)
    package2 = get_package(
        tracking_number="789",
        friendly_name="friendly name 2",
        status=40,
    )
    package3 = get_package(
        tracking_number="123",
        friendly_name="friendly name 3",
        status=20,
    )
    mock_seventeentrack.return_value.profile.packages.return_value = [
        package1,
        package2,
        package3,
    ]
