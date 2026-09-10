"""Test manual removal of ScorpionTrack vehicles."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyscorpiontrack import ScorpionTrackConnectionError, ScorpionTrackShare
import pytest

from homeassistant.components.scorpiontrack.const import DEFAULT_SCAN_INTERVAL, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import WebSocketGenerator


@pytest.mark.parametrize("latitude", [51.5074, None])
async def test_shared_vehicle_cannot_be_removed(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    latitude: float | None,
) -> None:
    """Protect shared vehicles even when their GPS location is missing."""
    vehicle = mock_share.vehicles[0]
    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share,
        vehicles=(
            replace(vehicle, position=replace(vehicle.position, latitude=latitude)),
        ),
    )
    await setup_integration(hass, mock_config_entry)
    assert await async_setup_component(hass, "config", {})
    client = await hass_ws_client(hass)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "101_1"), mock_config_entry.entry_id
    )
    assert device is not None
    assert mock_config_entry.supports_remove_device

    result = await client.remove_device(device.id)

    assert not result["success"]
    assert device_registry.async_get(device.id) is not None
    mock_scorpiontrack_client.async_get_share.assert_awaited_once_with()


async def test_removal_requires_successful_update(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Do not allow removal using stale data after an update fails."""
    await setup_integration(hass, mock_config_entry)
    assert await async_setup_component(hass, "config", {})
    client = await hass_ws_client(hass)
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

    mock_scorpiontrack_client.async_get_share.side_effect = (
        ScorpionTrackConnectionError()
    )
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)
    result = await client.remove_device(device.id)
    assert not result["success"]
    assert device_registry.async_get(device.id) is not None

    mock_scorpiontrack_client.async_get_share.side_effect = None
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)
    result = await client.remove_device(device.id)
    await hass.async_block_till_done()
    assert result["success"]
    assert device_registry.async_get(device.id) is None
    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    mock_scorpiontrack_client.async_get_share.assert_awaited_with()
    assert mock_scorpiontrack_client.async_get_share.await_count == 4


async def test_deleted_vehicle_returns_after_reload(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Remove one share's device and restore a returning vehicle on reload."""
    await setup_integration(hass, mock_config_entry)
    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    original_ids = {entity.entity_id for entity in entities}
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
    assert await async_setup_component(hass, "config", {})
    client = await hass_ws_client(hass)
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
    result = await client.remove_device(device.id)
    await hass.async_block_till_done()
    assert result["success"]
    assert device_registry.async_get(device.id) is None
    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert all(hass.states.get(entity_id) is None for entity_id in original_ids)

    mock_scorpiontrack_client.async_get_share.return_value = mock_share
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert {
        entity.entity_id
        for entity in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    } == original_ids
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
    assert (
        er.async_entries_for_config_entry(entity_registry, other_entry.entry_id)
        == other_entities
    )
    assert mock_scorpiontrack_client.async_get_share.await_count == 4


async def test_unloaded_entry_cannot_remove_devices(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Reject removal when the integration is not loaded."""
    await setup_integration(hass, mock_config_entry)
    assert await async_setup_component(hass, "config", {})
    client = await hass_ws_client(hass)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "101_1"), mock_config_entry.entry_id
    )
    assert device is not None
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await client.remove_device(device.id)

    assert not result["success"]
    assert device_registry.async_get(device.id) is not None
