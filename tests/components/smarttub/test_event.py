"""Test the SmartTub event platform."""

from datetime import datetime, timedelta
from unittest.mock import create_autospec

from pytest_homeassistant.common import MockConfigEntry, async_capture_events
import smarttub

from homeassistant.const import EVENT_STATE_CHANGED, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import trigger_update


def _make_error(code: int, title: str, updated_at: datetime) -> smarttub.SpaError:
    """Create a mock entry in the error history."""
    error = create_autospec(smarttub.SpaError, instance=True)
    error.code = code
    error.title = title
    error.description = "Description"
    error.active = True
    error.created_at = dt_util.utcnow() - timedelta(days=1)
    error.updated_at = updated_at
    error.error_type = "TUB_ERROR"
    return error


async def test_error_event(
    spa, config_entry: MockConfigEntry, hass: HomeAssistant
) -> None:
    """Test events for new and updated errors, and none for existing ones."""
    old_error = _make_error(1002, "AC POWER DISCONNECTED", dt_util.utcnow())
    spa.get_errors.return_value = [old_error]

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = f"event.{spa.brand}_{spa.model}_error"
    state = hass.states.get(entity_id)
    assert state is not None
    # errors present at startup are not reported
    assert state.state == STATE_UNKNOWN

    # an unchanged history does not fire
    await trigger_update(hass)
    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    # a new error fires
    new_error = _make_error(11, "Flow Switch Stuck Open", dt_util.utcnow())
    spa.get_errors.return_value = [old_error, new_error]
    await trigger_update(hass)
    state = hass.states.get(entity_id)
    assert state.state != STATE_UNKNOWN
    assert state.attributes["event_type"] == "error"
    assert state.attributes["error_code"] == 11
    assert state.attributes["error_title"] == "Flow Switch Stuck Open"
    assert state.attributes["error_description"] == "Description"
    assert state.attributes["error_type"] == "TUB_ERROR"
    first_state = state.state

    # nothing new: no further event
    await trigger_update(hass)
    assert hass.states.get(entity_id).state == first_state

    # a known error reported again fires
    old_error.updated_at = dt_util.utcnow() + timedelta(minutes=5)
    await trigger_update(hass)
    state = hass.states.get(entity_id)
    assert state.state != first_state
    assert state.attributes["error_code"] == 1002


async def test_multiple_errors_in_one_poll(
    spa, config_entry: MockConfigEntry, hass: HomeAssistant
) -> None:
    """Test every new error is published, not only the last one in a poll."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = f"event.{spa.brand}_{spa.model}_error"
    changes = async_capture_events(hass, EVENT_STATE_CHANGED)

    now = dt_util.utcnow()
    spa.get_errors.return_value = [
        _make_error(12, "Second", now + timedelta(minutes=1)),
        _make_error(11, "First", now),
    ]
    await trigger_update(hass)

    codes = [
        event.data["new_state"].attributes["error_code"]
        for event in changes
        if event.data["entity_id"] == entity_id
    ]
    assert codes == [11, 12]
