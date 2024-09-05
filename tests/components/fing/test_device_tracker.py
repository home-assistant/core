"""Test Fing Agent device tracker entity."""

from homeassistant.components.fing.coordinator import FingDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration
from .const import mocked_dev_resp_del_dev, mocked_dev_resp_new_dev


async def test_device_tracker_init(
    hass: HomeAssistant,
    mocked_entry,
    mocked_fing_agent_new_api,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Fing device tracker setup."""
    entry = await init_integration(hass, mocked_entry, mocked_fing_agent_new_api)
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 3


async def test_new_device_found(
    hass: HomeAssistant,
    mocked_entry,
    mocked_fing_agent_new_api,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Fing device tracker setup."""
    entry = await init_integration(hass, mocked_entry, mocked_fing_agent_new_api)
    coordinator: FingDataUpdateCoordinator = entry.runtime_data
    # First check -> there are 3 devices in total
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 3

    mocked_fing_agent_new_api.get_devices.return_value = mocked_dev_resp_new_dev()

    await coordinator.async_refresh()
    # Second check -> added one device
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 4

    mocked_fing_agent_new_api.get_devices.return_value = mocked_dev_resp_del_dev()

    await coordinator.async_refresh()
    # Third check -> removed two devices (old devices)
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 2
