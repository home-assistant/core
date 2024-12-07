"""Test for Trafikverket Train component Init."""

from __future__ import annotations

from unittest.mock import patch

from pytrafikverket.exceptions import InvalidAuthentication, NoTrainStationFound
from pytrafikverket.models import TrainStopModel
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.trafikverket_train.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from . import ENTRY_CONFIG, OPTIONS_CONFIG

from tests.common import MockConfigEntry


async def test_unload_entry(
    hass: HomeAssistant, get_trains: list[TrainStopModel]
) -> None:
    """Test unload an entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        options=OPTIONS_CONFIG,
        entry_id="1",
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_search_train_station",
        ),
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_get_next_train_stops",
            return_value=get_trains,
        ) as mock_tv_train,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert len(mock_tv_train.mock_calls) == 1

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_auth_failed(
    hass: HomeAssistant,
    get_trains: list[TrainStopModel],
    snapshot: SnapshotAssertion,
) -> None:
    """Test authentication failed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        options=OPTIONS_CONFIG,
        entry_id="1",
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_search_train_station",
        side_effect=InvalidAuthentication,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR

    active_flows = entry.async_get_active_flows(hass, (SOURCE_REAUTH))
    for flow in active_flows:
        assert flow == snapshot


async def test_no_stations(
    hass: HomeAssistant,
    get_trains: list[TrainStopModel],
    snapshot: SnapshotAssertion,
) -> None:
    """Test stations are missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        options=OPTIONS_CONFIG,
        entry_id="1",
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_search_train_station",
        side_effect=NoTrainStationFound,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_migrate_entity_unique_id(
    hass: HomeAssistant,
    get_trains: list[TrainStopModel],
    snapshot: SnapshotAssertion,
    entity_registry: EntityRegistry,
) -> None:
    """Test migration of entity unique id in old format."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        options=OPTIONS_CONFIG,
        entry_id="1",
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)

    entity = entity_registry.async_get_or_create(
        DOMAIN,
        "sensor",
        "incorrect_unique_id",
        config_entry=entry,
        original_name="Stockholm C to Uppsala C",
    )

    with (
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_search_train_station",
        ),
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_get_next_train_stops",
            return_value=get_trains,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    entity = entity_registry.async_get(entity.entity_id)
    assert entity.unique_id == f"{entry.entry_id}-departure_time"


async def test_migrate_entry(
    hass: HomeAssistant,
    get_trains: list[TrainStopModel],
) -> None:
    """Test migrate entry unique id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        options=OPTIONS_CONFIG,
        version=1,
        minor_version=1,
        entry_id="1",
        unique_id="321",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_search_train_station",
        ),
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_get_next_train_stops",
            return_value=get_trains,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    assert entry.version == 1
    assert entry.minor_version == 2
    assert entry.unique_id is None


async def test_migrate_entry_from_future_version_fails(
    hass: HomeAssistant,
    get_trains: list[TrainStopModel],
) -> None:
    """Test migrate entry from future version fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        options=OPTIONS_CONFIG,
        version=2,
        entry_id="1",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_search_train_station",
        ),
        patch(
            "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_get_next_train_stops",
            return_value=get_trains,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.MIGRATION_ERROR
