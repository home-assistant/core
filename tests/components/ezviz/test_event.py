"""Tests for EZVIZ event entities."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pyezvizapi.exceptions import PyEzvizError
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)

from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers.event import async_track_state_change_event

from . import setup_integration
from .test_init import _mock_camera_data

ENTITY_ID = "event.camera_1_motion"
SERIAL = "C123456789"


def _camera(
    last_alarm_time: str | None, status: int = 1
) -> dict[str, dict[str, object]]:
    """Return coordinator data with the given last alarm."""
    return {
        SERIAL: _mock_camera_data(
            status=status,
            last_alarm_time=last_alarm_time,
            last_alarm_type_code="10079",
            last_alarm_type_name="Smart Detection Alarm",
        )
    }


async def _refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_ezviz_client: AsyncMock,
    last_alarm_time: str | None,
    status: int = 1,
) -> None:
    """Let the coordinator fetch new camera data."""
    mock_ezviz_client.load_cameras.return_value = _camera(last_alarm_time, status)
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_event_on_new_alarm(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test an event is fired only when the camera reports a new alarm."""
    freezer.move_to("2026-11-17 12:00:00+00:00")
    mock_ezviz_client.load_cameras.return_value = _camera("2026-11-17 10:00:00")

    await setup_integration(hass, mock_config_entry)

    # The alarm already there at startup is not a new event
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    await _refresh(hass, freezer, mock_ezviz_client, "2026-11-17 10:00:00")
    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN

    await _refresh(hass, freezer, mock_ezviz_client, "2026-11-17 12:00:20")
    state = hass.states.get(ENTITY_ID)
    assert state.state == "2026-11-17T12:01:00.000+00:00"
    assert state.attributes[ATTR_EVENT_TYPE] == "motion"
    assert state.attributes["alarm_time"] == "2026-11-17 12:00:20"
    assert state.attributes["alarm_type_code"] == "10079"
    assert state.attributes["alarm_type_name"] == "Smart Detection Alarm"

    # A missing alarm time and the same alarm coming back do not fire again
    await _refresh(hass, freezer, mock_ezviz_client, None)
    await _refresh(hass, freezer, mock_ezviz_client, "2026-11-17 12:00:20")
    assert hass.states.get(ENTITY_ID).state == "2026-11-17T12:01:00.000+00:00"


async def test_event_after_outage(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test a new alarm in the first refresh after an outage is a separate change."""
    freezer.move_to("2026-11-17 12:00:00+00:00")
    mock_ezviz_client.load_cameras.return_value = _camera("2026-11-17 10:00:00")

    await setup_integration(hass, mock_config_entry)

    mock_ezviz_client.load_cameras.side_effect = PyEzvizError("outage")
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    changes: list[tuple[str | None, str]] = []

    @callback
    def _record(event: Event[EventStateChangedData]) -> None:
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]
        assert new_state is not None
        changes.append((old_state.state if old_state else None, new_state.state))

    async_track_state_change_event(hass, ENTITY_ID, _record)

    mock_ezviz_client.load_cameras.side_effect = None
    await _refresh(hass, freezer, mock_ezviz_client, "2026-11-17 12:00:40")

    assert changes == [
        (STATE_UNAVAILABLE, STATE_UNKNOWN),
        (STATE_UNKNOWN, "2026-11-17T12:01:00.000+00:00"),
    ]


async def test_event_kept_while_camera_offline(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test an alarm reported while the camera is offline fires when it is back."""
    freezer.move_to("2026-11-17 12:00:00+00:00")
    mock_ezviz_client.load_cameras.return_value = _camera("2026-11-17 10:00:00")

    await setup_integration(hass, mock_config_entry)

    changes: list[tuple[str | None, str]] = []

    @callback
    def _record(event: Event[EventStateChangedData]) -> None:
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]
        assert new_state is not None
        changes.append((old_state.state if old_state else None, new_state.state))

    async_track_state_change_event(hass, ENTITY_ID, _record)

    # The camera is offline: the new alarm is not consumed yet
    await _refresh(hass, freezer, mock_ezviz_client, "2026-11-17 12:00:20", status=2)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    # Back online with the same alarm: it fires as a separate state change
    await _refresh(hass, freezer, mock_ezviz_client, "2026-11-17 12:00:20")

    assert changes == [
        (STATE_UNKNOWN, STATE_UNAVAILABLE),
        (STATE_UNAVAILABLE, STATE_UNKNOWN),
        (STATE_UNKNOWN, "2026-11-17T12:01:00.000+00:00"),
    ]


async def test_handled_alarm_restored_after_reload(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test an alarm handled before a reload does not fire again.

    The first refresh after the reload has no alarm time, then the camera
    reports the alarm that was already handled.
    """
    freezer.move_to("2026-11-17 12:00:00+00:00")
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(ENTITY_ID, "2026-11-17T11:00:00.000+00:00"),
                {
                    "last_event_type": "motion",
                    "last_event_attributes": {
                        "alarm_time": "2026-11-17 11:00:00",
                        "alarm_type_code": "10079",
                        "alarm_type_name": "Smart Detection Alarm",
                    },
                    "last_alarm_time": "2026-11-17 11:00:00",
                },
            )
        ],
    )
    mock_ezviz_client.load_cameras.return_value = _camera(None)

    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == "2026-11-17T11:00:00.000+00:00"

    await _refresh(hass, freezer, mock_ezviz_client, "2026-11-17 11:00:00")
    assert hass.states.get(ENTITY_ID).state == "2026-11-17T11:00:00.000+00:00"

    # A new alarm still fires
    await _refresh(hass, freezer, mock_ezviz_client, "2026-11-17 12:00:30")
    assert hass.states.get(ENTITY_ID).state == "2026-11-17T12:01:00.000+00:00"


async def test_startup_alarm_not_fired_after_reload(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_ezviz_client: AsyncMock,
) -> None:
    """Test the alarm skipped at startup does not fire after a reload.

    It was never fired, so it is not in the event attributes: the handled
    alarm is stored on its own.
    """
    freezer.move_to("2026-11-17 12:00:00+00:00")
    mock_ezviz_client.load_cameras.return_value = _camera("2026-11-17 10:00:00")

    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN

    # The first refresh after the reload has no alarm time
    mock_ezviz_client.load_cameras.return_value = _camera(None)
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await _refresh(hass, freezer, mock_ezviz_client, "2026-11-17 10:00:00")
    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN
