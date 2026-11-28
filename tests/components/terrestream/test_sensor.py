"""Test Terrestream measurements and availability."""

import asyncio
from copy import deepcopy
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion
from terrestream_local.errors import AuthenticationError, ClientError
from terrestream_local.models import Snapshot

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import UUID

ENTITY = "sensor.terrestream_carbon_dioxide"
LIGHT = "sensor.terrestream_illuminance"


@pytest.mark.usefixtures("mock_client")
async def test_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Expose the supported measurements and stable device identity."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 12
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
    device = device_registry.async_get_device_by_identifier(
        ("terrestream", UUID), config_entry.entry_id
    )
    assert device is not None
    assert device == snapshot(name="device")


@pytest.mark.parametrize(
    "status", ["missing", "warming", "cleaning", "invalid", "stale"]
)
async def test_measurement_unavailable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    status: str,
) -> None:
    """Hide unavailable measurements without affecting other readings."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    updated: Snapshot = deepcopy(mock_client.refresh.return_value)
    updated["measurements"]["co2"] = {"available": False, "status": status}
    mock_client.refresh.return_value = updated
    freezer.tick(31)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY).state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.terrestream_illuminance").state == "100"


async def test_expired_on_receipt(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Do not publish a reading that expired in transit."""
    mock_client.measurement_available.side_effect = None
    mock_client.measurement_available.return_value = False
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == STATE_UNAVAILABLE


async def test_zero_measurement(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Keep a valid zero distinct from a missing measurement."""
    mock_client.refresh.return_value["measurements"]["illuminance"]["value"] = 0
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.terrestream_illuminance").state == "0"


async def test_offline_poll_and_recovery(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Mark a failed poll unavailable and recover on a successful poll."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_client.refresh.side_effect = ClientError("offline")
    freezer.tick(31)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY).state == STATE_UNAVAILABLE
    mock_client.refresh.side_effect = None
    freezer.tick(31)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY).state == "500"


async def test_revoked_pairing_during_refresh(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Stop exposing readings when an established credential is revoked."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_client.refresh.side_effect = AuthenticationError("revoked")
    freezer.tick(31)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY).state == STATE_UNAVAILABLE


async def test_polling_interval(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Read every 30 seconds without issuing clock commands between polls."""
    freezer.move_to("2026-01-01T00:00:00.500000+00:00")
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_client.refresh.assert_awaited_once()
    assert hass.states.get(LIGHT).state == "100"

    freezer.tick(29)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_client.refresh.assert_awaited_once()
    assert hass.states.get(LIGHT).state == "100"

    updated: Snapshot = deepcopy(mock_client.refresh.return_value)
    updated["measurements"]["illuminance"]["value"] = 200
    mock_client.refresh.return_value = updated
    freezer.tick(1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_client.refresh.await_count == 2
    assert hass.states.get(LIGHT).state == "200"
    mock_client.command.assert_not_awaited()


async def test_delayed_refresh_publishes_one_snapshot(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Keep the last observation until the next poll has completed."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    updated: Snapshot = deepcopy(mock_client.refresh.return_value)
    updated["measurements"]["illuminance"]["value"] = 200
    refresh_started = asyncio.Event()
    finish_refresh = asyncio.Event()

    async def blocked_refresh() -> Snapshot:
        mock_client.measurement_available.side_effect = None
        mock_client.measurement_available.return_value = False
        refresh_started.set()
        await finish_refresh.wait()
        mock_client.measurement_available.return_value = True
        return updated

    mock_client.refresh.side_effect = blocked_refresh
    freezer.tick(31)
    async_fire_time_changed(hass)
    await refresh_started.wait()
    try:
        await hass.async_block_till_done()
        assert hass.states.get(LIGHT).state == "100"
    finally:
        finish_refresh.set()
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(LIGHT).state == "200"
    mock_client.command.assert_not_awaited()
