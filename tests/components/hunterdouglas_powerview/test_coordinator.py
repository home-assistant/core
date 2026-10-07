from unittest.mock import MagicMock, patch

from aiopvapi.resources.shade_data import PowerviewShadeData

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
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="powerview_hub_123",
        data={"host": "192.168.1.50"},
    )
    config_entry.add_to_hass(hass)

    # Setup our mock parent hub device in the registry
    hub_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "hub_serial_123")},
        name="PowerView Hub",
    )

    # Pre-populate Device A: Stale shade that will vanish on the next sync cycle
    stale_shade_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, 999)},  # Int matches your set key comparison loop
        name="Old Stale Shade",
        via_device_id=hub_device.id,
    )

    # Pre-populate Device B: Active shade that will stay on the hub
    active_shade_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, 111)},
        name="Active Living Room Shade",
        via_device_id=hub_device.id,
    )

    # Mock the underlying api client library classes
    mock_shades_api = MagicMock()
    mock_hub_api = MagicMock()
    mock_hub_api.hub_address = "192.168.1.50"

    coordinator = PowerviewShadeUpdateCoordinator(
        hass, config_entry, mock_shades_api, mock_hub_api
    )
    
    # Initialize the coordinator data object container
    coordinator.data = PowerviewShadeData()

    # Step 1: Simulate first run update where BOTH shades exist 
    # (This fills up coordinator._previous_shade_ids)
    first_run_mock_data = MagicMock()
    first_run_mock_data.raw = {111: {"id": 111}, 999: {"id": 999}}
    
    with patch.object(mock_shades_api, "get_shades", return_value=first_run_mock_data):
        await coordinator._async_update_data()
        assert coordinator._previous_shade_ids == {111, 999}

    # Step 2: Simulate second run update where shade 999 disappears from the hub api payload
    second_run_mock_data = MagicMock()
    second_run_mock_data.raw = {111: {"id": 111}}  # 999 is missing!

    with patch.object(mock_shades_api, "get_shades", return_value=second_run_mock_data):
        await coordinator._async_update_data()

    # Step 3: Assertions to validate cleanup execution
    # Active shade must still be present in the registry
    assert device_registry.async_get(active_shade_device.id) is not None
    
    # Stale shade config entry relation must be decoupled or missing entirely
    stale_device_lookup = device_registry.async_get(stale_shade_device.id)
    if stale_device_lookup:
        assert config_entry.entry_id not in stale_device_lookup.config_entries
