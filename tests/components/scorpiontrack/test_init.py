"""Test ScorpionTrack integration setup."""

from dataclasses import replace
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pyscorpiontrack import (
    ScorpionTrackConnectionError,
    ScorpionTrackInvalidTokenError,
    ScorpionTrackShare,
    ScorpionTrackShareUnavailableError,
)
import pytest

from homeassistant.components.scorpiontrack.const import DEFAULT_SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup and unload of entry."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_device_is_registered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the ScorpionTrack vehicle device is registered."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        ("scorpiontrack", "101_1"), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.name == "AB12 CDE"
    assert device.manufacturer == "Volkswagen"
    assert device.model == "Golf R"


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (ScorpionTrackInvalidTokenError("Invalid token"), ConfigEntryState.SETUP_ERROR),
        (
            ScorpionTrackShareUnavailableError("Share expired"),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            ScorpionTrackConnectionError("Connection failed"),
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
)
async def test_setup_entry_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scorpiontrack_client: AsyncMock,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup with token and connection errors."""
    mock_scorpiontrack_client.async_get_share.side_effect = exception

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is expected_state


@pytest.mark.parametrize(
    "entity_id",
    [
        "device_tracker.xy34_abc",
        "sensor.xy34_abc_speed",
        "sensor.xy34_abc_last_reported",
        "binary_sensor.xy34_abc_ignition",
    ],
)
async def test_vehicle_added_after_setup(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    entity_id: str,
) -> None:
    """Test discovery, repeat updates, returning vehicles, and reload."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(entity_id) is None
    initial_entities = len(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    )

    added_vehicle = replace(mock_share.vehicles[0], id=2, registration="XY34 ABC")
    updated_share = replace(mock_share, vehicles=(*mock_share.vehicles, added_vehicle))
    mock_scorpiontrack_client.async_get_share.return_value = updated_share
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    registry_entry = entity_registry.async_get(entity_id)
    assert registry_entry is not None
    device = device_registry.async_get_device_by_identifier(
        ("scorpiontrack", "101_2"), mock_config_entry.entry_id
    )
    assert device is not None
    assert registry_entry.device_id == device.id
    heading = entity_registry.async_get("sensor.xy34_abc_heading")
    assert heading is not None
    assert heading.device_id == device.id
    assert heading.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(heading.entity_id) is None
    assert mock_scorpiontrack_client.async_get_share.await_count == 2

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (
        len(
            er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
        )
        == initial_entities * 2
    )

    mock_scorpiontrack_client.async_get_share.return_value = mock_share
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    mock_scorpiontrack_client.async_get_share.return_value = updated_share
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == state.state
    assert entity_registry.async_get(entity_id).id == registry_entry.id
    assert (
        len(
            er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
        )
        == initial_entities * 2
    )

    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == state.state
    assert entity_registry.async_get(entity_id).id == registry_entry.id


async def test_discovery_stops_on_unload(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test unloading removes the discovery listeners."""
    await setup_integration(hass, mock_config_entry)
    initial_entities = len(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    )
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    added_vehicle = replace(mock_share.vehicles[0], id=2, registration="XY34 ABC")
    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share, vehicles=(*mock_share.vehicles, added_vehicle)
    )
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_scorpiontrack_client.async_get_share.assert_awaited_once_with()
    assert (
        len(
            er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
        )
        == initial_entities
    )
