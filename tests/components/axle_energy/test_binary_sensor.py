"""Test event activity and scheduled state changes."""

from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aioaxlevpp import AxleAuthenticationError, AxleConnectionError, GridEvent
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import (
    CONF_API_KEY,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "binary_sensor.axle_energy_event_in_progress"


async def setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Load the integration and all its platforms."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.freeze_time("2026-09-11T16:59:00Z")
async def test_binary_sensor_snapshot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Register the sensor with a stable identity and translated name."""
    with patch(
        "homeassistant.components.axle_energy.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        pytest.param("2026-09-11T16:59:59Z", STATE_OFF, id="before"),
        pytest.param("2026-09-11T17:00:00Z", STATE_ON, id="start"),
        pytest.param("2026-09-11T17:30:00Z", STATE_ON, id="during"),
        pytest.param("2026-09-11T18:00:00Z", STATE_OFF, id="end"),
        pytest.param("2026-09-11T18:00:01Z", STATE_OFF, id="after"),
    ],
)
@pytest.mark.parametrize("direction", ["import", "export"])
async def test_initial_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    mock_event: GridEvent,
    freezer: FrozenDateTimeFactory,
    now: str,
    expected: str,
    direction: str,
) -> None:
    """Evaluate the cached event immediately when Home Assistant starts."""
    freezer.move_to(now)
    mock_client.get_event.return_value = replace(mock_event, direction=direction)
    await setup(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == expected


@pytest.mark.freeze_time("2026-09-11T16:59:00Z")
async def test_boundaries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    mock_event: GridEvent,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Change at both boundaries without polling the API."""
    mock_client.get_event.return_value = replace(
        mock_event, end=mock_event.start + timedelta(minutes=1)
    )
    await setup(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    mock_client.get_event.reset_mock()

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON
    mock_client.get_event.assert_not_called()

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    mock_client.get_event.assert_not_called()


@pytest.mark.parametrize(
    "event_factory",
    [
        pytest.param(lambda event: None, id="no-event"),
        pytest.param(lambda event: replace(event, opted_out=True), id="opted-out"),
    ],
)
@pytest.mark.freeze_time("2026-09-11T17:00:00Z")
async def test_no_participating_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    mock_event: GridEvent,
    event_factory: Callable[[GridEvent], GridEvent | None],
) -> None:
    """An empty or opted-out event is off and remains available."""
    mock_client.get_event.return_value = event_factory(mock_event)
    await setup(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == STATE_OFF


@pytest.mark.freeze_time("2026-09-11T17:00:00Z")
@pytest.mark.parametrize(
    "event_factory",
    [
        pytest.param(lambda event: None, id="no-event"),
        pytest.param(lambda event: replace(event, opted_out=True), id="opted-out"),
    ],
)
@pytest.mark.parametrize(
    "start_offset",
    [pytest.param(0, id="active-event"), pytest.param(11, id="future-event")],
)
async def test_cancel_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    mock_event: GridEvent,
    freezer: FrozenDateTimeFactory,
    event_factory: Callable[[GridEvent], GridEvent | None],
    start_offset: int,
) -> None:
    """Cancel pending boundaries when an event is removed or opted out of."""
    mock_client.get_event.return_value = replace(
        mock_event, start=mock_event.start + timedelta(minutes=start_offset)
    )
    await setup(hass, mock_config_entry)
    mock_client.get_event.return_value = event_factory(mock_event)
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_OFF


@pytest.mark.freeze_time("2026-09-11T17:00:00Z")
async def test_revised_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    mock_event: GridEvent,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Replace both boundaries when Axle publishes a revised schedule."""
    mock_client.get_event.return_value = replace(
        mock_event,
        start=mock_event.start + timedelta(minutes=11),
        end=mock_event.start + timedelta(minutes=12),
    )
    await setup(hass, mock_config_entry)
    mock_client.get_event.return_value = replace(
        mock_event,
        start=mock_event.start + timedelta(minutes=13),
        end=mock_event.start + timedelta(minutes=14),
    )
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    mock_client.get_event.reset_mock()

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    mock_client.get_event.assert_not_called()


@pytest.mark.freeze_time("2026-09-11T17:00:00Z")
@pytest.mark.parametrize(
    "error",
    [
        pytest.param(AxleConnectionError(), id="connection"),
        pytest.param(AxleAuthenticationError(), id="authentication"),
    ],
)
async def test_unavailable_at_boundary(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    mock_event: GridEvent,
    freezer: FrozenDateTimeFactory,
    error: Exception,
) -> None:
    """A stale schedule must not report a healthy state after a failed poll."""
    mock_client.get_event.return_value = replace(
        mock_event, start=mock_event.start + timedelta(minutes=11)
    )
    await setup(hass, mock_config_entry)
    mock_client.get_event.side_effect = error
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.freeze_time("2026-09-11T17:00:00Z")
async def test_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    mock_event: GridEvent,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Resume boundary tracking after a connection failure."""
    await setup(hass, mock_config_entry)
    mock_client.get_event.side_effect = AxleConnectionError()
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    mock_client.get_event.side_effect = None
    mock_client.get_event.return_value = replace(
        mock_event, start=mock_event.start + timedelta(minutes=21)
    )
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON


@pytest.mark.freeze_time("2026-09-11T16:59:00Z")
async def test_unload_reload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Cancel a pending boundary on unload and recompute on reload."""
    await setup(hass, mock_config_entry)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_client.get_event.reset_mock()
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    mock_client.get_event.assert_not_called()

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON


@pytest.mark.freeze_time("2026-09-11T16:59:00Z")
async def test_independent_timers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    mock_event: GridEvent,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Unloading one feed must not cancel another feed's boundary timer."""
    await setup(hass, mock_config_entry)
    mock_client.get_event.return_value = replace(
        mock_event, start=mock_event.start + timedelta(minutes=1)
    )
    other = MockConfigEntry(
        domain="axle_energy", title="Other feed", data={CONF_API_KEY: "other-token"}
    )
    await setup(hass, other)
    other_entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", "axle_energy", f"{other.entry_id}_event_in_progress"
    )
    assert other_entity_id is not None
    assert other_entity_id != ENTITY_ID
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON
    assert hass.states.get(other_entity_id).state == STATE_OFF
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(other_entity_id).state == STATE_ON


@pytest.mark.freeze_time("2026-09-11T16:59:00Z")
async def test_disable_enable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Keep a disabled entity absent and restore its current state on enable."""
    await setup(hass, mock_config_entry)
    entity_registry.async_update_entity(
        ENTITY_ID, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID) is None

    entity_registry.async_update_entity(ENTITY_ID, disabled_by=None)
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON
