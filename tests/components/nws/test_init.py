"""Tests for init module."""

import pytest

from homeassistant.components.nws.const import (
    CONF_LOCATION_ENTITY,
    CONF_STATION,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import NWS_CONFIG

from tests.common import MockConfigEntry


@pytest.fixture
def location_entity_config(hass: HomeAssistant) -> dict:
    """Create a person entity in the registry and return a config dict using its registry ID."""
    registry = er.async_get(hass)
    entry = registry.async_get_or_create("person", "person", "test_user")
    registry.async_get_or_create("person", "person", "other_user")
    return {
        "entry": entry,
        "config": {
            CONF_API_KEY: "test",
            "latitude": 35,
            "longitude": -75,
            CONF_LOCATION_ENTITY: entry.id,
        },
        "config_with_station": {
            CONF_API_KEY: "test",
            "latitude": 35,
            "longitude": -75,
            CONF_LOCATION_ENTITY: entry.id,
            CONF_STATION: "ABC",
        },
    }


async def test_unload_entry(hass: HomeAssistant, mock_simple_nws) -> None:
    """Test that nws setup with config yaml."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_with_location_entity(
    hass: HomeAssistant, mock_simple_nws, location_entity_config: dict
) -> None:
    """Test setup resolves coordinates from location entity."""
    entity = location_entity_config["entry"]
    hass.states.async_set(
        entity.entity_id,
        "home",
        {ATTR_LATITUDE: 40.0, ATTR_LONGITUDE: -80.0},
    )

    config_entry = MockConfigEntry(domain=DOMAIN, data=location_entity_config["config"])
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    call_args = mock_simple_nws.call_args
    assert call_args[0][0] == 40.0
    assert call_args[0][1] == -80.0

    assert config_entry.runtime_data.latitude == 40.0
    assert config_entry.runtime_data.longitude == -80.0


async def test_setup_with_location_entity_auto_station(
    hass: HomeAssistant, mock_simple_nws, location_entity_config: dict
) -> None:
    """Test entity-based setup without explicit station calls set_station(None)."""
    entity = location_entity_config["entry"]
    hass.states.async_set(
        entity.entity_id,
        "home",
        {ATTR_LATITUDE: 40.0, ATTR_LONGITUDE: -80.0},
    )

    config_entry = MockConfigEntry(domain=DOMAIN, data=location_entity_config["config"])
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    mock_instance = mock_simple_nws.return_value
    mock_instance.set_station.assert_called_once_with(None)


async def test_setup_with_location_entity_explicit_station(
    hass: HomeAssistant, mock_simple_nws, location_entity_config: dict
) -> None:
    """Test entity-based setup with explicit station uses that station."""
    entity = location_entity_config["entry"]
    hass.states.async_set(
        entity.entity_id,
        "home",
        {ATTR_LATITUDE: 40.0, ATTR_LONGITUDE: -80.0},
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=location_entity_config["config_with_station"]
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    mock_instance = mock_simple_nws.return_value
    mock_instance.set_station.assert_called_once_with("ABC")


async def test_setup_with_location_entity_unavailable(
    hass: HomeAssistant, mock_simple_nws, location_entity_config: dict
) -> None:
    """Test setup falls back to stored coordinates when entity is unavailable."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=location_entity_config["config"])
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data.latitude == 35
    assert config_entry.runtime_data.longitude == -75


async def test_location_change_updates_coordinates(
    hass: HomeAssistant, mock_simple_nws, location_entity_config: dict
) -> None:
    """Test that a significant location change updates the API without reload."""
    entity = location_entity_config["entry"]
    hass.states.async_set(
        entity.entity_id,
        "home",
        {ATTR_LATITUDE: 40.0, ATTR_LONGITUDE: -80.0},
    )

    config_entry = MockConfigEntry(domain=DOMAIN, data=location_entity_config["config"])
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert mock_simple_nws.call_count == 1

    hass.states.async_set(
        entity.entity_id,
        "away",
        {ATTR_LATITUDE: 41.0, ATTR_LONGITUDE: -81.0},
    )
    await config_entry.runtime_data.coordinator_observation.async_refresh()
    await hass.async_block_till_done()

    assert mock_simple_nws.call_count == 2
    second_call = mock_simple_nws.call_args_list[1]
    assert second_call[0][0] == 41.0
    assert second_call[0][1] == -81.0
    assert config_entry.runtime_data.latitude == 41.0
    assert config_entry.runtime_data.longitude == -81.0


async def test_location_change_within_threshold_no_update(
    hass: HomeAssistant, mock_simple_nws, location_entity_config: dict
) -> None:
    """Test that a small location change does not create a new API instance."""
    entity = location_entity_config["entry"]
    hass.states.async_set(
        entity.entity_id,
        "home",
        {ATTR_LATITUDE: 40.0, ATTR_LONGITUDE: -80.0},
    )

    config_entry = MockConfigEntry(domain=DOMAIN, data=location_entity_config["config"])
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set(
        entity.entity_id,
        "home",
        {ATTR_LATITUDE: 40.0001, ATTR_LONGITUDE: -80.0001},
    )
    await config_entry.runtime_data.coordinator_observation.async_refresh()
    await hass.async_block_till_done()

    assert mock_simple_nws.call_count == 1
    assert config_entry.runtime_data.latitude == 40.0
    assert config_entry.runtime_data.longitude == -80.0


async def test_location_entity_becomes_unavailable_no_update(
    hass: HomeAssistant, mock_simple_nws, location_entity_config: dict
) -> None:
    """Test that entity becoming unavailable does not update coordinates."""
    entity = location_entity_config["entry"]
    hass.states.async_set(
        entity.entity_id,
        "home",
        {ATTR_LATITUDE: 40.0, ATTR_LONGITUDE: -80.0},
    )

    config_entry = MockConfigEntry(domain=DOMAIN, data=location_entity_config["config"])
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set(entity.entity_id, "unknown", {})
    await config_entry.runtime_data.coordinator_observation.async_refresh()
    await hass.async_block_till_done()

    assert mock_simple_nws.call_count == 1
    assert config_entry.runtime_data.latitude == 40.0
    assert config_entry.runtime_data.longitude == -80.0


async def test_same_coordinates_no_update(
    hass: HomeAssistant, mock_simple_nws, location_entity_config: dict
) -> None:
    """Test that unchanged coordinates do not create a new API instance."""
    entity = location_entity_config["entry"]
    hass.states.async_set(
        entity.entity_id,
        "home",
        {ATTR_LATITUDE: 40.0, ATTR_LONGITUDE: -80.0},
    )

    config_entry = MockConfigEntry(domain=DOMAIN, data=location_entity_config["config"])
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set(
        entity.entity_id,
        "away",
        {ATTR_LATITUDE: 40.0, ATTR_LONGITUDE: -80.0},
    )
    await config_entry.runtime_data.coordinator_observation.async_refresh()
    await hass.async_block_till_done()

    assert mock_simple_nws.call_count == 1


async def test_unload_with_location_entity(
    hass: HomeAssistant, mock_simple_nws, location_entity_config: dict
) -> None:
    """Test unload works cleanly with a location entity configured."""
    entity = location_entity_config["entry"]
    hass.states.async_set(
        entity.entity_id,
        "home",
        {ATTR_LATITUDE: 40.0, ATTR_LONGITUDE: -80.0},
    )

    config_entry = MockConfigEntry(domain=DOMAIN, data=location_entity_config["config"])
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
