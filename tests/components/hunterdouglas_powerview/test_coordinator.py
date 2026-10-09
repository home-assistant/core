"""Tests for the Hunter Douglas PowerView data update coordinator and device cleanup."""

from unittest.mock import ASyncMock, MagicMock

from homeassistant.components.hunterdouglas_powerview.const import DOMAIN
from homeassistant.components.hunterdouglas_powerview.coordinator import (
    PowerviewShadeUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_coordinator_automatic_cleanup_stale_shades(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test that the coordinator automatically removes devices when shades vanish from the hub."""
    config_entry = MockConfigEntry(domain=DOMAIN, unique_id="hub_123")
    config_entry.add_to_hass(hass)

    # Setup our mock parent hub device in the registry
    hub_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "hub_123")},
    )

    # Pre-populate Device A: Stale shade that will vanish on the next sync cycle
    stale_shade_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, 999)},
        via_device_id=hub_device.id,
    )

    # Pre-populate Device B: Active shade that will stay on the hub
    active_shade_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, 111)},
        via_device_id=hub_device.id,
    )

    # Mock the underlying api client library classes
    mock_shades_api = MagicMock()
    mock_hub_api = MagicMock()
    mock_hub_api.hub_address = "192.168.1.50"

    coordinator = PowerviewShadeUpdateCoordinator(
        hass, config_entry, mock_shades_api, mock_hub_api
    )

    # The mock hub payload only returns one of the two shades defined
    mock_data = MagicMock()
    mock_data.shades = {111: {"id": 111}}
    coordinator.data = mock_data

    # Set up the async-safe mock return data payload
    mock_api_payload = MagicMock()
    mock_shades_api.get_shades = AsyncMock(return_value=mock_api_payload)
    
    # Execute the coordinator update sequence pass
    await coordinator._async_update_data()

    # Assertion 1: Active shade must still be present in the registry
    assert device_registry.async_get(active_shade_device.id) is not None

    # Assertion 2: Stale shade must be removed from the registry
    assert device_registry.async_get(stale_shade_device.id) is None
