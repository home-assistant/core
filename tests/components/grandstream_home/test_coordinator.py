# mypy: ignore-errors
"""Test the Grandstream Home coordinator module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.grandstream_home.const import DOMAIN
from homeassistant.components.grandstream_home.coordinator import GrandstreamCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="ec:74:d7:97:53:c5",
        data={
            "host": "192.168.1.100",
            "device_model": "gds",
        },
    )


@pytest.fixture
def mock_api():
    """Create a mock API."""
    api = MagicMock()
    api.host = "192.168.1.100"
    return api


async def test_coordinator_init(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test coordinator initialization."""
    coordinator = GrandstreamCoordinator(
        hass=hass,
        entry=mock_config_entry,
        api=mock_api,
        unique_id="ec:74:d7:97:53:c5",
        discovery_version="1.0.1.6",
    )

    assert coordinator.entry_id == mock_config_entry.entry_id
    assert coordinator._api == mock_api
    assert coordinator._unique_id == "ec:74:d7:97:53:c5"
    assert coordinator._discovery_version == "1.0.1.6"
    assert coordinator._error_count == 0


async def test_coordinator_update_data_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test coordinator successful data update."""
    coordinator = GrandstreamCoordinator(
        hass=hass,
        entry=mock_config_entry,
        api=mock_api,
        unique_id="ec:74:d7:97:53:c5",
    )

    with patch(
        "homeassistant.components.grandstream_home.coordinator.fetch_gds_status",
        return_value={
            "phone_status": "idle",
            "version": "1.0.1.6",
        },
    ):
        data = await coordinator._async_update_data()

    assert data["phone_status"] == "idle"
    assert coordinator._error_count == 0


async def test_coordinator_update_data_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test coordinator data update failure."""
    coordinator = GrandstreamCoordinator(
        hass=hass,
        entry=mock_config_entry,
        api=mock_api,
        unique_id="ec:74:d7:97:53:c5",
    )

    with patch(
        "homeassistant.components.grandstream_home.coordinator.fetch_gds_status",
        return_value=None,
    ):
        data = await coordinator._async_update_data()

    assert data == {"phone_status": "unknown"}
    assert coordinator._error_count == 1


async def test_coordinator_update_data_exception(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test coordinator data update with exception."""
    coordinator = GrandstreamCoordinator(
        hass=hass,
        entry=mock_config_entry,
        api=mock_api,
        unique_id="ec:74:d7:97:53:c5",
    )

    with patch(
        "homeassistant.components.grandstream_home.coordinator.fetch_gds_status",
        side_effect=RuntimeError("Connection failed"),
    ):
        data = await coordinator._async_update_data()

    assert "phone_status" in data
    assert data["phone_status"] == "unknown"


async def test_coordinator_error_threshold(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test coordinator error threshold handling."""
    coordinator = GrandstreamCoordinator(
        hass=hass,
        entry=mock_config_entry,
        api=mock_api,
        unique_id="ec:74:d7:97:53:c5",
    )

    # Simulate multiple failures to reach threshold
    with patch(
        "homeassistant.components.grandstream_home.coordinator.fetch_gds_status",
        return_value=None,
    ):
        for _ in range(3):
            data = await coordinator._async_update_data()

    # After threshold reached, should return unavailable
    assert data["phone_status"] == "unavailable"


async def test_coordinator_firmware_version_update(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test coordinator updates firmware version in device registry."""
    mock_config_entry.add_to_hass(hass)

    # Create device in registry
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "ec:74:d7:97:53:c5")},
        name="Test Device",
    )

    coordinator = GrandstreamCoordinator(
        hass=hass,
        entry=mock_config_entry,
        api=mock_api,
        unique_id="ec:74:d7:97:53:c5",
    )

    with patch(
        "homeassistant.components.grandstream_home.coordinator.fetch_gds_status",
        return_value={
            "phone_status": "idle",
            "version": "1.0.1.7",
        },
    ):
        await coordinator._async_update_data()

    # Check device registry was updated
    updated_device = device_registry.async_get(device.id)
    assert updated_device.sw_version == "1.0.1.7"


async def test_coordinator_firmware_version_none(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test coordinator handles None firmware version."""
    coordinator = GrandstreamCoordinator(
        hass=hass,
        entry=mock_config_entry,
        api=mock_api,
        unique_id="ec:74:d7:97:53:c5",
    )

    # Call with None version - should not raise and not update
    coordinator._update_firmware_version(None)
    coordinator._update_firmware_version("")  # Empty string should also return


async def test_coordinator_handle_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test coordinator error handling method."""
    coordinator = GrandstreamCoordinator(
        hass=hass,
        entry=mock_config_entry,
        api=mock_api,
        unique_id="ec:74:d7:97:53:c5",
    )

    # First error should return unknown
    result = coordinator._handle_error("phone_status")
    assert result == {"phone_status": "unknown"}
    assert coordinator._error_count == 1

    # After threshold, should return unavailable
    coordinator._error_count = 3
    result = coordinator._handle_error("phone_status")
    assert result == {"phone_status": "unavailable"}


async def test_coordinator_discovery_version_fallback(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test coordinator uses discovery version as fallback."""
    coordinator = GrandstreamCoordinator(
        hass=hass,
        entry=mock_config_entry,
        api=mock_api,
        unique_id="ec:74:d7:97:53:c5",
        discovery_version="1.0.1.5",
    )

    # When API returns no version, should use discovery_version
    with patch(
        "homeassistant.components.grandstream_home.coordinator.fetch_gds_status",
        return_value={
            "phone_status": "idle",
            # No version key
        },
    ):
        await coordinator._async_update_data()

    # The _update_firmware_version should be called with discovery_version
    # when result has no version
