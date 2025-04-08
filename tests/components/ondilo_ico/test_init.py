"""Test Ondilo ICO initialization."""

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from ondilo import OndiloError
import pytest
from syrupy import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_devices(
    hass: HomeAssistant,
    mock_ondilo_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test devices are registered."""
    await setup_integration(hass, config_entry, mock_ondilo_client)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    assert len(device_entries) == 2

    for device_entry in device_entries:
        identifier = list(device_entry.identifiers)[0]
        assert device_entry == snapshot(name=f"{identifier[0]}-{identifier[1]}")


async def test_get_pools_error(
    hass: HomeAssistant,
    mock_ondilo_client: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test get pools errors."""
    mock_ondilo_client.get_pools.side_effect = OndiloError(
        502,
        (
            "<html> <head><title>502 Bad Gateway</title></head> "
            "<body> <center><h1>502 Bad Gateway</h1></center> </body> </html>"
        ),
    )
    await setup_integration(hass, config_entry, mock_ondilo_client)

    # No sensor should be created
    assert not hass.states.async_all()
    # We should not have tried to retrieve pool measures
    assert mock_ondilo_client.get_ICO_details.call_count == 0
    assert mock_ondilo_client.get_last_pool_measures.call_count == 0
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_init_with_no_ico_attached(
    hass: HomeAssistant,
    mock_ondilo_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    pool1: dict[str, Any],
) -> None:
    """Test if an ICO is not attached to a pool, then no sensor is created."""
    # Only one pool, but no ICO attached
    mock_ondilo_client.get_pools.return_value = pool1
    mock_ondilo_client.get_ICO_details.side_effect = None
    mock_ondilo_client.get_ICO_details.return_value = None
    await setup_integration(hass, config_entry, mock_ondilo_client)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    # No devices should be created
    assert len(device_entries) == 0
    # No sensor should be created
    assert len(hass.states.async_all()) == 0
    # We should not have tried to retrieve pool measures
    mock_ondilo_client.get_last_pool_measures.assert_not_called()
    assert config_entry.state is ConfigEntryState.LOADED


async def test_adding_pool_after_setup(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_ondilo_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    pool1: dict[str, Any],
    two_pools: list[dict[str, Any]],
    ico_details1: dict[str, Any],
    ico_details2: dict[str, Any],
) -> None:
    """Test adding one pool after integration setup."""
    mock_ondilo_client.get_pools.return_value = pool1
    mock_ondilo_client.get_ICO_details.return_value = ico_details1

    await setup_integration(hass, config_entry, mock_ondilo_client)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    # One pool is created with 7 entities.
    assert len(device_entries) == 1
    assert len(hass.states.async_all()) == 7

    mock_ondilo_client.get_pools.return_value = two_pools
    mock_ondilo_client.get_ICO_details.return_value = ico_details2

    # Trigger a refresh of the pools coordinator.
    freezer.tick(timedelta(minutes=20))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    # Two pool have been created with 7 entities each.
    assert len(device_entries) == 2
    assert len(hass.states.async_all()) == 14


async def test_removing_pool_after_setup(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_ondilo_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    pool1: dict[str, Any],
    ico_details1: dict[str, Any],
) -> None:
    """Test removing one pool after integration setup."""
    await setup_integration(hass, config_entry, mock_ondilo_client)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    # Two pools are created with 7 entities each.
    assert len(device_entries) == 2
    assert len(hass.states.async_all()) == 14

    mock_ondilo_client.get_pools.return_value = pool1
    mock_ondilo_client.get_ICO_details.return_value = ico_details1

    # Trigger a refresh of the pools coordinator.
    freezer.tick(timedelta(minutes=20))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    # One pool is left with 7 entities.
    assert len(device_entries) == 1
    assert len(hass.states.async_all()) == 7


@pytest.mark.parametrize(
    ("api", "devices", "config_entry_state"),
    [
        ("get_ICO_details", 0, ConfigEntryState.SETUP_RETRY),
        ("get_last_pool_measures", 1, ConfigEntryState.LOADED),
    ],
)
async def test_details_error_all_pools(
    hass: HomeAssistant,
    mock_ondilo_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    pool1: dict[str, Any],
    api: str,
    devices: int,
    config_entry_state: ConfigEntryState,
) -> None:
    """Test details and measures error for all pools."""
    mock_ondilo_client.get_pools.return_value = pool1
    client_api = getattr(mock_ondilo_client, api)
    client_api.side_effect = OndiloError(400, "error")

    await setup_integration(hass, config_entry, mock_ondilo_client)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    assert len(device_entries) == devices
    assert config_entry.state is config_entry_state


async def test_details_error_one_pool(
    hass: HomeAssistant,
    mock_ondilo_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    ico_details2: dict[str, Any],
) -> None:
    """Test details error for one pool and success for the other."""
    mock_ondilo_client.get_ICO_details.side_effect = [
        OndiloError(
            404,
            "Not Found",
        ),
        ico_details2,
    ]

    await setup_integration(hass, config_entry, mock_ondilo_client)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    assert len(device_entries) == 1


async def test_measures_error_one_pool(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_ondilo_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    last_measures: list[dict[str, Any]],
) -> None:
    """Test measures error for one pool and success for the other."""
    entity_id_1 = "sensor.pool_1_temperature"
    entity_id_2 = "sensor.pool_2_temperature"
    mock_ondilo_client.get_last_pool_measures.side_effect = [
        OndiloError(
            404,
            "Not Found",
        ),
        last_measures,
    ]

    await setup_integration(hass, config_entry, mock_ondilo_client)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    assert len(device_entries) == 2
    # One pool returned an error, the other is ok.
    # 7 entities are created for the second pool.
    assert len(hass.states.async_all()) == 7
    assert hass.states.get(entity_id_1) is None
    assert hass.states.get(entity_id_2) is not None

    # All pools now return measures.
    mock_ondilo_client.get_last_pool_measures.side_effect = None

    # Move time to next pools coordinator refresh.
    freezer.tick(timedelta(minutes=20))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    assert len(device_entries) == 2
    # 14 entities in total, 7 entities per pool.
    assert len(hass.states.async_all()) == 14
    assert hass.states.get(entity_id_1) is not None
    assert hass.states.get(entity_id_2) is not None


async def test_measures_scheduling(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_ondilo_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test refresh scheduling of measures coordinator."""
    # Move time to 10 min after pool 1 was updated and 5 min after pool 2 was updated.
    freezer.move_to("2024-01-01T01:10:00+00:00")
    entity_id_1 = "sensor.pool_1_temperature"
    entity_id_2 = "sensor.pool_2_temperature"
    await setup_integration(hass, config_entry, mock_ondilo_client)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    # Two pools are created with 7 entities each.
    assert len(device_entries) == 2
    assert len(hass.states.async_all()) == 14

    state = hass.states.get(entity_id_1)
    assert state is not None
    assert state.last_reported == datetime.fromisoformat("2024-01-01T01:10:00+00:00")
    state = hass.states.get(entity_id_2)
    assert state is not None
    assert state.last_reported == datetime.fromisoformat("2024-01-01T01:10:00+00:00")

    # Tick time by 20 min.
    # The measures coordinators for both pools should not have been refreshed again.
    freezer.tick(timedelta(minutes=20))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id_1)
    assert state is not None
    assert state.last_reported == datetime.fromisoformat("2024-01-01T01:10:00+00:00")
    state = hass.states.get(entity_id_2)
    assert state is not None
    assert state.last_reported == datetime.fromisoformat("2024-01-01T01:10:00+00:00")

    # Move time to 65 min after pool 1 was last updated.
    # This is 5 min after we expect pool 1 to be updated again.
    # The measures coordinator for pool 1 should refresh at this time.
    # The measures coordinator for pool 2 should not have been refreshed again.
    # The pools coordinator has updated the last update time
    # of the pools to a stale time that is already passed.
    freezer.move_to("2024-01-01T02:05:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id_1)
    assert state is not None
    assert state.last_reported == datetime.fromisoformat("2024-01-01T02:05:00+00:00")
    state = hass.states.get(entity_id_2)
    assert state is not None
    assert state.last_reported == datetime.fromisoformat("2024-01-01T01:10:00+00:00")

    # Tick time by 5 min.
    # The measures coordinator for pool 1 should not have been refreshed again.
    # The measures coordinator for pool 2 should refresh at this time.
    # The pools coordinator has updated the last update time
    # of the pools to a stale time that is already passed.
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id_1)
    assert state is not None
    assert state.last_reported == datetime.fromisoformat("2024-01-01T02:05:00+00:00")
    state = hass.states.get(entity_id_2)
    assert state is not None
    assert state.last_reported == datetime.fromisoformat("2024-01-01T02:10:00+00:00")

    # Tick time by 55 min.
    # The measures coordinator for pool 1 should refresh at this time.
    # This is 1 hour after the last refresh of the measures coordinator for pool 1.
    freezer.tick(timedelta(minutes=55))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id_1)
    assert state is not None
    assert state.last_reported == datetime.fromisoformat("2024-01-01T03:05:00+00:00")
    state = hass.states.get(entity_id_2)
    assert state is not None
    assert state.last_reported == datetime.fromisoformat("2024-01-01T02:10:00+00:00")

    # Tick time by 5 min.
    # The measures coordinator for pool 2 should refresh at this time.
    # This is 1 hour after the last refresh of the measures coordinator for pool 2.
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id_1)
    assert state is not None
    assert state.last_reported == datetime.fromisoformat("2024-01-01T03:05:00+00:00")
    state = hass.states.get(entity_id_2)
    assert state is not None
    assert state.last_reported == datetime.fromisoformat("2024-01-01T03:10:00+00:00")

    # Set an error on the pools coordinator endpoint.
    # This will cause the pools coordinator to not update the next refresh.
    # This should cause the measures coordinators to keep the 1 hour cadence.
    mock_ondilo_client.get_pools.side_effect = OndiloError(
        502,
        (
            "<html> <head><title>502 Bad Gateway</title></head> "
            "<body> <center><h1>502 Bad Gateway</h1></center> </body> </html>"
        ),
    )

    # Tick time by 55 min.
    # The measures coordinator for pool 1 should refresh at this time.
    # This is 1 hour after the last refresh of the measures coordinator for pool 1.
    freezer.tick(timedelta(minutes=55))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id_1)
    assert state is not None
    assert state.last_reported == datetime.fromisoformat("2024-01-01T04:05:00+00:00")
    state = hass.states.get(entity_id_2)
    assert state is not None
    assert state.last_reported == datetime.fromisoformat("2024-01-01T03:10:00+00:00")

    # Tick time by 5 min.
    # The measures coordinator for pool 2 should refresh at this time.
    # This is 1 hour after the last refresh of the measures coordinator for pool 2.
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id_1)
    assert state is not None
    assert state.last_reported == datetime.fromisoformat("2024-01-01T04:05:00+00:00")
    state = hass.states.get(entity_id_2)
    assert state is not None
    assert state.last_reported == datetime.fromisoformat("2024-01-01T04:10:00+00:00")
