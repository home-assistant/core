"""Test the DLNA DMR component setup and cleanup."""

from unittest.mock import Mock

from homeassistant.components import media_player
from homeassistant.components.dlna_dmr.const import DOMAIN as DLNA_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_resource_lifecycle(
    hass: HomeAssistant,
    domain_data_mock: Mock,
    config_entry_mock: MockConfigEntry,
    ssdp_scanner_mock: Mock,
    dmr_device_mock: Mock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that resources are acquired/released as the entity is setup/unloaded."""
    # Set up the config entry
    config_entry_mock.add_to_hass(hass)
    assert await async_setup_component(hass, DLNA_DOMAIN, {}) is True
    await hass.async_block_till_done()

    # Check the entity is created and working
    entries = er.async_entries_for_config_entry(
        entity_registry, config_entry_mock.entry_id
    )
    assert len(entries) == 1
    entity_id = entries[0].entity_id

    await async_update_entity(hass, entity_id)
    await hass.async_block_till_done()

    mock_state = hass.states.get(entity_id)
    assert mock_state is not None
    assert mock_state.state == media_player.STATE_IDLE

    # Check update listeners and event notifiers are subscribed
    assert len(config_entry_mock.update_listeners) == 1
    assert domain_data_mock.async_get_event_notifier.await_count == 1
    assert domain_data_mock.async_release_event_notifier.await_count == 0
    assert ssdp_scanner_mock.async_register_callback.await_count == 2
    assert ssdp_scanner_mock.async_register_callback.return_value.call_count == 0
    assert dmr_device_mock.async_subscribe_services.await_count == 1
    assert dmr_device_mock.async_unsubscribe_services.await_count == 0
    assert dmr_device_mock.on_event is not None

    # Unload the config entry
    assert await hass.config_entries.async_remove(config_entry_mock.entry_id) == {
        "require_restart": False
    }

    # Check update listeners and event notifiers are released
    assert not config_entry_mock.update_listeners
    assert domain_data_mock.async_get_event_notifier.await_count == 1
    assert domain_data_mock.async_release_event_notifier.await_count == 1
    assert ssdp_scanner_mock.async_register_callback.await_count == 2
    assert ssdp_scanner_mock.async_register_callback.return_value.call_count == 2
    assert dmr_device_mock.async_subscribe_services.await_count == 1
    assert dmr_device_mock.async_unsubscribe_services.await_count == 1
    assert dmr_device_mock.on_event is None
