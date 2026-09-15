"""Tests for recorder session recovery."""

from datetime import timedelta
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from sqlalchemy.exc import SQLAlchemyError

from homeassistant.components.recorder import get_instance, history
from homeassistant.components.recorder.db_schema import States
from homeassistant.components.recorder.util import session_scope
from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

from .common import async_wait_recording_done

from tests.typing import RecorderInstanceContextManager


@pytest.fixture
async def mock_recorder_before_hass(
    async_test_recorder: RecorderInstanceContextManager,
) -> None:
    """Set up recorder."""


@pytest.mark.usefixtures("recorder_mock")
async def test_oldest_ts_preserved_after_sqlalchemy_recovery(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test oldest_ts is not reseeded from now after session recovery."""
    instance = get_instance(hass)
    entity_id = "sensor.oldest_ts_recovery"
    stable_entity_id = "sensor.oldest_ts_stable"

    hass.states.async_set(stable_entity_id, "on")
    hass.states.async_set(entity_id, "before")
    await async_wait_recording_done(hass)

    oldest_ts_before_recovery = instance.states_manager.oldest_ts
    assert oldest_ts_before_recovery is not None

    freezer.tick(timedelta(seconds=1))
    start_time = dt_util.utcnow()

    event_session = instance.event_session
    assert event_session is not None

    def _throw_if_state_in_session(*args: Any, **kwargs: Any) -> None:
        for obj in event_session:
            if isinstance(obj, States):
                raise SQLAlchemyError(
                    "insert the state", "fake params", "forced to fail"
                )

    with (
        patch("time.sleep"),
        patch.object(
            event_session,
            "flush",
            side_effect=_throw_if_state_in_session,
        ),
    ):
        hass.states.async_set(entity_id, "fail")
        await async_wait_recording_done(hass)

    assert "SQLAlchemyError error processing task" in caplog.text

    freezer.tick(timedelta(seconds=1))
    hass.states.async_set(entity_id, "after")
    await async_wait_recording_done(hass)

    assert instance.states_manager.oldest_ts == oldest_ts_before_recovery

    with session_scope(hass=hass, read_only=True) as session:
        recorded_states = {row.state for row in session.query(States)}
    assert "fail" not in recorded_states

    hist = history.get_significant_states(
        hass,
        start_time,
        dt_util.utcnow(),
        entity_ids=[entity_id, stable_entity_id],
        include_start_time_state=True,
    )
    start_state = hist[entity_id][0]
    assert isinstance(start_state, State)
    assert start_state.state == "before"
    stable_start_state = hist[stable_entity_id][0]
    assert isinstance(stable_start_state, State)
    assert stable_start_state.state == "on"
