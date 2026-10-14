"""Test automatic removal of ScorpionTrack vehicles."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyscorpiontrack import (
    ScorpionTrackConnectionError,
    ScorpionTrackInvalidTokenError,
    ScorpionTrackShare,
    ScorpionTrackShareUnavailableError,
)
import pytest

from homeassistant.components.scorpiontrack.const import DEFAULT_SCAN_INTERVAL, DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize("latitude", [51.5074, None])
async def test_shared_vehicle_is_kept(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    latitude: float | None,
) -> None:
    """Keep shared vehicles even when their GPS location is missing."""
    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "101_1"), mock_config_entry.entry_id
    )
    assert device is not None
    vehicle = mock_share.vehicles[0]
    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share,
        vehicles=(
            replace(vehicle, position=replace(vehicle.position, latitude=latitude)),
        ),
    )

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert device_registry.async_get(device.id) == device
    assert mock_scorpiontrack_client.async_get_share.await_count == 2


@pytest.mark.parametrize(
    "exception",
    [
        ScorpionTrackConnectionError(),
        ScorpionTrackInvalidTokenError(),
        ScorpionTrackShareUnavailableError(),
    ],
)
async def test_failed_update_keeps_devices(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    exception: Exception,
) -> None:
    """Remove absent vehicles only once a successful update confirms it."""
    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "101_1"), mock_config_entry.entry_id
    )
    assert device is not None
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    mock_scorpiontrack_client.async_get_share.side_effect = exception

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert device_registry.async_get(device.id) == device
    assert (
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
        == entities
    )
    assert hass.states.get("sensor.ab12_cde_speed").state == STATE_UNAVAILABLE

    mock_scorpiontrack_client.async_get_share.side_effect = None
    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share, vehicles=()
    )
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert device_registry.async_get(device.id) is None
    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )


async def test_removed_vehicle_returns(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Remove only this share's device and rediscover it without a reload."""
    await setup_integration(hass, mock_config_entry)
    entity_registry.async_update_entity(
        "sensor.ab12_cde_speed", new_entity_id="sensor.vehicle_speed", name="My speed"
    )
    await hass.async_block_till_done()
    original_entities = {
        entity.entity_id: entity.id
        for entity in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    }
    other_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="202", data={"share_token": "other-token"}
    )
    other_client = AsyncMock()
    other_client.async_get_share.return_value = replace(mock_share, id=202)
    with patch(
        "homeassistant.components.scorpiontrack.ScorpionTrackClient",
        return_value=other_client,
    ):
        await setup_integration(hass, other_entry)
    other_entities = er.async_entries_for_config_entry(
        entity_registry, other_entry.entry_id
    )
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "101_1"), mock_config_entry.entry_id
    )
    assert device is not None

    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share, vehicles=()
    )
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert device_registry.async_get(device.id) is None
    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert all(hass.states.get(entity_id) is None for entity_id in original_entities)
    assert er.async_entries_for_config_entry(entity_registry, other_entry.entry_id) == (
        other_entities
    )

    mock_scorpiontrack_client.async_get_share.return_value = mock_share
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert {
        entity.entity_id: entity.id
        for entity in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    } == original_entities
    assert hass.states.get("sensor.vehicle_speed").state != STATE_UNAVAILABLE
    assert entity_registry.async_get("sensor.vehicle_speed").name == "My speed"
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "101_1"), mock_config_entry.entry_id
        )
        is not None
    )
    assert (
        entity_registry.async_get("sensor.ab12_cde_heading").disabled_by
        is er.RegistryEntryDisabler.INTEGRATION
    )
    assert er.async_entries_for_config_entry(entity_registry, other_entry.entry_id) == (
        other_entities
    )
    assert mock_scorpiontrack_client.async_get_share.await_count == 3


async def test_vehicle_removed_while_unloaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Clean up saved devices absent from the first successful setup response."""
    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "101_1"), mock_config_entry.entry_id
    )
    assert device is not None
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share, vehicles=()
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert device_registry.async_get(device.id) is None
    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
