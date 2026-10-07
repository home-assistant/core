"""Test the Skylight calendar platform."""

from datetime import timedelta
import itertools
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from skylight_api import SkylightAPIError

from homeassistant.components.calendar import (
    DOMAIN as CALENDAR_DOMAIN,
    SERVICE_GET_EVENTS,
    CalendarEntityFeature,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import EVENT_END, EVENT_START

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_coordinator_data")
async def test_calendar_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the calendar entity is set up."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("calendar.home_frame_calendar")
    assert state is not None
    assert state.state == "off"


@pytest.mark.usefixtures("mock_coordinator_data")
async def test_calendar_get_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test calendar.get_events returns the coordinator's events."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            "entity_id": "calendar.home_frame_calendar",
            "start_date_time": EVENT_START - timedelta(days=1),
            "end_date_time": EVENT_END + timedelta(days=1),
        },
        blocking=True,
        return_response=True,
    )
    events = result["calendar.home_frame_calendar"]["events"]
    assert events == [
        {
            "start": EVENT_START.isoformat(),
            "end": EVENT_END.isoformat(),
            "summary": "Family dinner",
            "description": "At grandma's",
        }
    ]


@pytest.mark.usefixtures("mock_coordinator_data")
async def test_calendar_is_read_only(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entity is read-only: no write features are advertised."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("calendar.home_frame_calendar")
    features = int(state.attributes.get("supported_features") or 0)
    assert features & CalendarEntityFeature.CREATE_EVENT == 0
    assert features & CalendarEntityFeature.UPDATE_EVENT == 0
    assert features & CalendarEntityFeature.DELETE_EVENT == 0


async def test_coordinator_setup_retry_then_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failing API call retries with backoff and then recovers."""
    raw_events = {
        "data": [
            {
                "id": "event-1",
                "attributes": {
                    "summary": "Family dinner",
                    "starts_at": "2026-10-10T09:00:00+00:00",
                    "ends_at": "2026-10-10T10:00:00+00:00",
                },
            }
        ]
    }
    with patch(
        "skylight_api.SkylightAPI.get_calendar_events",
        side_effect=itertools.chain(
            [SkylightAPIError("boom")], itertools.repeat(raw_events)
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

        for _ in range(20):
            if mock_config_entry.state is ConfigEntryState.LOADED:
                break
            freezer.tick(timedelta(minutes=1))
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.LOADED
