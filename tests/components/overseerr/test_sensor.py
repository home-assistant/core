"""Test the Overseerr sensor platform."""
from unittest.mock import MagicMock

from homeassistant.components.overseerr.const import DOMAIN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_entity_registry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    overseerr_request_data: MagicMock,
) -> None:
    """Tests that the devices are registered in the entity registry."""
    config_entry.add_to_hass(hass)
    overseerr_request_data.side_effect = None

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success

    # Assert movie entity and state
    movie_entity: er.RegistryEntry = entity_registry.async_get(
        "sensor.mock_title_movie_requests"
    )
    assert movie_entity.unique_id == f"{config_entry.entry_id}-requested_movies"
    assert movie_entity.original_name == "Movie Requests"

    movie_state: State = hass.states.get("sensor.mock_title_movie_requests")
    assert movie_state

    # Assert TV entity and state
    tv_entity: er.RegistryEntry = entity_registry.async_get(
        "sensor.mock_title_tv_show_requests"
    )
    assert tv_entity.unique_id == f"{config_entry.entry_id}-requested_tv"
    assert tv_entity.original_name == "TV Show Requests"

    tv_state: State = hass.states.get("sensor.mock_title_tv_show_requests")
    assert tv_state

    # Assert approved entity and state
    approved_entity: er.RegistryEntry = entity_registry.async_get(
        "sensor.mock_title_approved_requests"
    )
    assert approved_entity.unique_id == f"{config_entry.entry_id}-requested_approved"
    assert approved_entity.original_name == "Approved Requests"

    approved_state: State = hass.states.get("sensor.mock_title_approved_requests")
    assert approved_state

    # Assert available entity and state
    available_entity: er.RegistryEntry = entity_registry.async_get(
        "sensor.mock_title_available_requests"
    )
    assert available_entity.unique_id == f"{config_entry.entry_id}-requested_available"
    assert available_entity.original_name == "Available Requests"

    available_state: State = hass.states.get("sensor.mock_title_available_requests")
    assert available_state

    # Assert pending entity and state
    pending_entity: er.RegistryEntry = entity_registry.async_get(
        "sensor.mock_title_pending_requests"
    )
    assert pending_entity.unique_id == f"{config_entry.entry_id}-requested_pending"
    assert pending_entity.original_name == "Pending Requests"

    pending_state: State = hass.states.get("sensor.mock_title_pending_requests")
    assert pending_state

    # Assert total entity and state
    total_entity: er.RegistryEntry = entity_registry.async_get(
        "sensor.mock_title_total_requests"
    )
    assert total_entity.unique_id == f"{config_entry.entry_id}-requested_total"
    assert total_entity.original_name == "Total Requests"

    total_state: State = hass.states.get("sensor.mock_title_total_requests")
    assert total_state
