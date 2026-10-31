"""Test the grid event calendar through Home Assistant."""

from dataclasses import replace
from datetime import timedelta
from http import HTTPStatus
from typing import Literal
from unittest.mock import AsyncMock, patch

from aioaxlevpp import AxleConnectionError, AxleStatus, GridEvent
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
    snapshot_platform,
)
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.calendar import (
    DOMAIN as CALENDAR_DOMAIN,
    EVENT_END_DATETIME,
    EVENT_START_DATETIME,
    SERVICE_GET_EVENTS,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceResponse
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

ENTITY_ID = "calendar.axle_energy_events"
EVENT = {
    "start": "2026-09-11T17:00:00+00:00",
    "end": "2026-09-11T18:00:00+00:00",
    "summary": "Export",
}


async def setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Load the integration and its platforms."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def get_events(
    hass: HomeAssistant,
    start: str = "2026-09-11T16:00:00Z",
    end: str = "2026-09-11T19:00:00Z",
) -> ServiceResponse:
    """Read the calendar through its public action."""
    response = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            EVENT_START_DATETIME: start,
            EVENT_END_DATETIME: end,
        },
        blocking=True,
        return_response=True,
    )
    assert response is not None
    return response


@pytest.mark.freeze_time("2026-09-11T16:59:00Z")
async def test_calendar_snapshot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Register the calendar with a stable identity and translated name."""
    with patch("homeassistant.components.axle_energy.PLATFORMS", [Platform.CALENDAR]):
        await setup(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("now", "expected_state", "direction", "expected_message"),
    [
        pytest.param(
            "2026-09-11T16:59:59Z", STATE_OFF, "import", "Import", id="before-import"
        ),
        pytest.param(
            "2026-09-11T16:59:59Z", STATE_OFF, "export", "Export", id="before-export"
        ),
        pytest.param(
            "2026-09-11T17:00:00Z", STATE_ON, "import", "Import", id="start-import"
        ),
        pytest.param(
            "2026-09-11T17:00:00Z", STATE_ON, "export", "Export", id="start-export"
        ),
        pytest.param(
            "2026-09-11T17:30:00Z", STATE_ON, "import", "Import", id="during-import"
        ),
        pytest.param(
            "2026-09-11T17:30:00Z", STATE_ON, "export", "Export", id="during-export"
        ),
        pytest.param(
            "2026-09-11T18:00:00Z", STATE_OFF, "import", None, id="end-import"
        ),
        pytest.param(
            "2026-09-11T18:00:00Z", STATE_OFF, "export", None, id="end-export"
        ),
        pytest.param(
            "2026-09-11T18:00:01Z", STATE_OFF, "import", None, id="after-import"
        ),
        pytest.param(
            "2026-09-11T18:00:01Z", STATE_OFF, "export", None, id="after-export"
        ),
    ],
)
async def test_current_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    mock_event: GridEvent,
    freezer: FrozenDateTimeFactory,
    now: str,
    expected_state: str,
    direction: Literal["import", "export"],
    expected_message: str | None,
) -> None:
    """Only current and upcoming events appear in the calendar state."""
    freezer.move_to(now)
    mock_client.get_status.return_value = AxleStatus(
        replace(mock_event, direction=direction), False
    )
    await setup(hass, mock_config_entry)
    state = hass.states.get(ENTITY_ID)
    assert state.state == expected_state
    assert state.attributes.get("message") == expected_message
    assert hass.states.get("sensor.axle_energy_event_type").state == direction


@pytest.mark.freeze_time("2026-09-11T16:59:00Z")
@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        pytest.param(
            "2026-09-11T16:00:00Z", "2026-09-11T19:00:00Z", [EVENT], id="contains"
        ),
        pytest.param(
            "2026-09-11T17:15:00Z", "2026-09-11T17:45:00Z", [EVENT], id="within"
        ),
        pytest.param(
            "2026-09-11T17:30:00Z", "2026-09-11T19:00:00Z", [EVENT], id="overlaps-end"
        ),
        pytest.param(
            "2026-09-11T16:00:00Z", "2026-09-11T17:30:00Z", [EVENT], id="overlaps-start"
        ),
        pytest.param(
            "2026-09-11T17:00:00Z", "2026-09-11T18:00:00Z", [EVENT], id="exact"
        ),
        pytest.param(
            "2026-09-11T16:00:00Z", "2026-09-11T17:00:00Z", [], id="ends-at-start"
        ),
        pytest.param(
            "2026-09-11T18:00:00Z", "2026-09-11T19:00:00Z", [EVENT], id="starts-at-end"
        ),
        pytest.param(
            "2026-09-11T18:00:01Z", "2026-09-11T19:00:00Z", [], id="after-end"
        ),
        pytest.param(
            "2026-09-11T18:00:00+01:00",
            "2026-09-11T19:00:00+01:00",
            [EVENT],
            id="local-time",
        ),
    ],
)
async def test_calendar_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    start: str,
    end: str,
    expected: list[dict[str, str]],
) -> None:
    """Include ending events for end triggers, excluding later ranges."""
    await setup(hass, mock_config_entry)
    mock_client.get_status.reset_mock()
    assert await get_events(hass, start, end) == {ENTITY_ID: {"events": expected}}
    mock_client.get_status.assert_not_called()


@pytest.mark.freeze_time("2026-09-11T16:59:00Z")
async def test_empty_range(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """An empty range requested by the calendar view returns no events."""
    await setup(hass, mock_config_entry)
    client = await hass_client()
    response = await client.get(
        f"/api/calendars/{ENTITY_ID}",
        params={"start": "2026-09-11T17:30:00Z", "end": "2026-09-11T17:30:00Z"},
    )
    assert response.status == HTTPStatus.OK
    assert await response.json() == []


@pytest.mark.freeze_time("2026-09-11T16:59:00Z")
@pytest.mark.parametrize(
    "opted_out",
    [
        pytest.param(False, id="opted-in"),
        pytest.param(None, id="unknown-participation"),
    ],
)
async def test_empty_schedule(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    opted_out: bool | None,
) -> None:
    """A healthy empty schedule is an available, inactive calendar."""
    mock_client.get_status.return_value = AxleStatus(None, opted_out)
    await setup(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    assert await get_events(hass) == {ENTITY_ID: {"events": []}}


@pytest.mark.freeze_time("2026-09-11T16:59:00Z")
async def test_opted_out(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    mock_event: GridEvent,
) -> None:
    """Preserve the shared feed's account opt-out filtering."""
    mock_client.get_status.return_value = AxleStatus(mock_event, True)
    await setup(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    assert await get_events(hass) == {ENTITY_ID: {"events": []}}
    assert hass.states.get("binary_sensor.axle_energy_participation").state == STATE_OFF


@pytest.mark.freeze_time("2026-09-11T16:59:00Z")
async def test_failure_and_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """An outage is unavailable, and a recovered feed returns its event."""
    await setup(hass, mock_config_entry)
    mock_client.get_status.side_effect = AxleConnectionError
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    client = await hass_client()
    response = await client.get(
        f"/api/calendars/{ENTITY_ID}",
        params={"start": "2026-09-11T16:00:00Z", "end": "2026-09-11T19:00:00Z"},
    )
    assert response.status == HTTPStatus.OK
    assert await response.json() == snapshot
    mock_client.get_status.side_effect = None
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ENTITY_ID).state == STATE_ON
    assert await get_events(hass) == {ENTITY_ID: {"events": [EVENT]}}


@pytest.mark.freeze_time("2026-09-11T16:59:00Z")
async def test_boundaries_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    mock_event: GridEvent,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Update event boundaries locally and remove the calendar on unload."""
    mock_client.get_status.return_value = AxleStatus(
        replace(mock_event, end=mock_event.start + timedelta(minutes=1)), False
    )
    await setup(hass, mock_config_entry)
    mock_client.get_status.reset_mock()
    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    assert "message" not in hass.states.get(ENTITY_ID).attributes
    mock_client.get_status.assert_not_called()
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(ENTITY_ID).attributes["restored"]
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_client.get_status.assert_not_called()


@pytest.mark.freeze_time("2026-09-11T16:59:00Z")
async def test_reload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A normal reload retains the calendar's registry identity."""
    await setup(hass, mock_config_entry)
    identity = entity_registry.async_get(ENTITY_ID)
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert entity_registry.async_get(ENTITY_ID).id == identity.id
    assert hass.states.get(ENTITY_ID).state == STATE_OFF


@pytest.mark.freeze_time("2026-09-11T16:59:00Z")
@pytest.mark.parametrize(
    ("event_type", "calls_after_start"),
    [
        pytest.param("start", 1, id="start"),
        pytest.param("end", 0, id="end"),
    ],
)
async def test_calendar_trigger(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    mock_event: GridEvent,
    freezer: FrozenDateTimeFactory,
    event_type: str,
    calls_after_start: int,
) -> None:
    """The standard calendar automation fires at the event boundary."""
    mock_client.get_status.return_value = AxleStatus(
        replace(mock_event, end=mock_event.start + timedelta(minutes=1)), False
    )
    await setup(hass, mock_config_entry)
    calls = async_mock_service(hass, "test", "automation")
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "triggers": [
                    {
                        "trigger": "calendar",
                        "entity_id": ENTITY_ID,
                        "event": event_type,
                    }
                ],
                "actions": {
                    "action": "test.automation",
                    "data": {"summary": "{{ trigger.calendar_event.summary }}"},
                },
            }
        },
    )
    await hass.async_block_till_done()
    mock_client.get_status.reset_mock()
    assert not calls
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(calls) == calls_after_start
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data == {"summary": "Export"}
    mock_client.get_status.assert_not_called()


@pytest.mark.freeze_time("2026-09-11T16:59:00Z")
@pytest.mark.parametrize(
    ("offset", "end_minutes"),
    [
        pytest.param("00:00:00", 14, id="no-offset"),
        pytest.param("00:05:00", 9, id="positive-offset"),
        pytest.param("-00:05:00", 19, id="negative-offset"),
    ],
)
async def test_end_trigger_at_scan_boundary(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    mock_event: GridEvent,
    freezer: FrozenDateTimeFactory,
    offset: str,
    end_minutes: int,
) -> None:
    """Fire an end trigger exactly at the next calendar scan window."""
    mock_client.get_status.return_value = AxleStatus(
        replace(mock_event, end=mock_event.start + timedelta(minutes=end_minutes)),
        False,
    )
    await setup(hass, mock_config_entry)
    calls = async_mock_service(hass, "test", "automation")
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "triggers": [
                    {
                        "trigger": "calendar",
                        "entity_id": ENTITY_ID,
                        "event": "end",
                        "offset": offset,
                    }
                ],
                "actions": {"action": "test.automation"},
            }
        },
    )
    await hass.async_block_till_done()
    assert not calls
    freezer.tick(timedelta(minutes=14, seconds=59))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert not calls
    mock_client.get_status.reset_mock()
    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(calls) == 1
    mock_client.get_status.assert_not_called()
