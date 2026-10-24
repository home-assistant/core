"""Test measurement availability and controller lifecycle."""

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

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import UUID

ENTITY = "sensor.terrestream_carbon_dioxide"


async def test_sensors_and_unload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Expose 12 measurements and release ownership on unload."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 12
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
    device = device_registry.async_get_device_by_identifier(
        ("terrestream", UUID), config_entry.entry_id
    )
    assert device is not None
    assert device == snapshot(name="device")
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    mock_client.command.assert_any_await("release")


async def test_pending_pairing(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Finish a pairing whose confirmation was interrupted."""
    mock_client.identity.return_value = {"paired": False}
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_client.confirm.assert_awaited_once()
    await hass.config_entries.async_unload(config_entry.entry_id)


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(AuthenticationError("revoked"), id="revoked"),
        pytest.param(ClientError("offline"), id="offline"),
    ],
)
async def test_setup_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    error: Exception,
) -> None:
    """Never expose measurements from an unauthenticated endpoint."""
    mock_client.identity.side_effect = error
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert not hass.states.async_all("sensor")


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
    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_expired_on_receipt(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Do not publish a reading that expired in transit."""
    mock_client.measurement_available.side_effect = None
    mock_client.measurement_available.return_value = False
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == STATE_UNAVAILABLE
    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_zero_measurement(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Keep a valid zero distinct from a missing measurement."""
    mock_client.refresh.return_value["measurements"]["illuminance"]["value"] = 0
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.terrestream_illuminance").state == "0"
    await hass.config_entries.async_unload(config_entry.entry_id)


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ClientError("offline"), id="offline"),
        pytest.param(AuthenticationError("revoked"), id="revoked"),
    ],
)
async def test_failed_first_refresh_releases_lease(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    error: ClientError,
) -> None:
    """A failed setup does not leave a live lease behind."""
    mock_client.refresh.side_effect = error
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    mock_client.command.assert_any_await("release")


async def test_shutdown_release(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Graceful shutdown releases ownership before the next HA starts."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    mock_client.command.assert_any_await("release")
    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_offline_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """An unreachable sensor does not prevent unloading HA entities."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_client.command.side_effect = ClientError("offline")
    assert await hass.config_entries.async_unload(config_entry.entry_id)


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
    await hass.config_entries.async_unload(config_entry.entry_id)


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
    await hass.config_entries.async_unload(config_entry.entry_id)
