"""Test measurement availability and controller lifecycle."""

from datetime import timedelta
from time import monotonic
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from terrestream_local.errors import AuthenticationError, ClientError
from terrestream_local.models import Snapshot

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import UUID

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY = "sensor.terrestream_indoor_air_quality_sensor_carbon_dioxide"


async def test_polling_preserves_illuminance_freshness(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Reduce polling while refreshing light before its 20-second expiry."""
    freezer.move_to("2026-01-01T00:00:00.500000+00:00")
    snapshot: Snapshot = mock_client.refresh.return_value
    lifetimes = dict.fromkeys(snapshot["measurements"], 60.0)
    lifetimes["illuminance"] = 20.0
    received = 0.0

    def remaining(key: str) -> float:
        return max(0, lifetimes[key] - (monotonic() - received))

    async def refresh() -> Snapshot:
        nonlocal received
        received = monotonic()
        return snapshot

    mock_client.refresh.side_effect = refresh
    mock_client.measurement_remaining.side_effect = remaining
    mock_client.measurement_available.side_effect = lambda key: remaining(key) > 0
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    light = "sensor.terrestream_indoor_air_quality_sensor_illuminance"
    assert hass.states.get(light).state == "100"
    mock_client.refresh.reset_mock()

    freezer.tick(14)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_client.refresh.assert_not_awaited()
    assert hass.states.get(light).state == "100"

    snapshot["measurements"]["illuminance"]["value"] = 200
    freezer.tick(1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_client.refresh.assert_awaited_once()
    assert hass.states.get(light).state == "200"

    freezer.tick(6)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_client.refresh.assert_awaited_once()
    assert hass.states.get(light).state == "200"
    assert await hass.config_entries.async_unload(config_entry.entry_id)


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
        ("terrestream_local", UUID), config_entry.entry_id
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


async def test_measurement_expiry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An invalid measurement becomes unavailable rather than zero."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_client.measurement_available.return_value = False
    freezer.tick(16)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY).state == STATE_UNAVAILABLE
    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_expiry_between_availability_and_state(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Evaluate freshness once so a deadline cannot produce an unknown state."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    entity = hass.data["entity_components"]["sensor"].get_entity(ENTITY)
    mock_client.measurement_available.side_effect = [True, False]

    entity.async_write_ha_state()
    assert hass.states.get(ENTITY).state == "500"

    entity.async_write_ha_state()
    assert hass.states.get(ENTITY).state == STATE_UNAVAILABLE
    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_failed_first_refresh_releases_lease(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """A failed setup does not leave a live lease behind."""
    mock_client.refresh.side_effect = ClientError("offline")
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


async def test_deadline_expires_without_another_poll(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Expire a cached value even between successful coordinator polls."""
    mock_client.measurement_remaining.return_value = 1.0
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == "500"
    mock_client.refresh.reset_mock()
    mock_client.measurement_available.return_value = False
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == STATE_UNAVAILABLE
    mock_client.refresh.assert_not_awaited()
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
    freezer.tick(16)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY).state == STATE_UNAVAILABLE
    await hass.config_entries.async_unload(config_entry.entry_id)
