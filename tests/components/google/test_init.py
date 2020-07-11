"""The tests for the Google Calendar component."""
import pytest

import homeassistant.components.google as google
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.setup import async_setup_component

from tests.async_mock import patch


@pytest.fixture(name="google_setup")
def mock_google_setup(hass):
    """Mock the google set up functions."""
    p_auth = patch(
        "homeassistant.components.google.do_authentication", side_effect=google.do_setup
    )
    p_service = patch("homeassistant.components.google.GoogleCalendarService.get")
    p_discovery = patch("homeassistant.components.google.discovery.load_platform")
    p_load = patch("homeassistant.components.google.load_config", return_value={})
    p_save = patch("homeassistant.components.google.update_config")

    with p_auth, p_load, p_service, p_discovery, p_save:
        yield


async def test_setup_component(hass, google_setup):
    """Test setup component."""
    config = {"google": {CONF_CLIENT_ID: "id", CONF_CLIENT_SECRET: "secret"}}

    assert await async_setup_component(hass, "google", config)


async def test_get_calendar_info(hass, test_calendar):
    """Test getting the calendar info."""
    calendar_info = await hass.async_add_executor_job(
        google.get_calendar_info, hass, test_calendar
    )
    assert calendar_info == {
        "cal_id": "qwertyuiopasdfghjklzxcvbnm@import.calendar.google.com",
        "entities": [
            {
                "device_id": "we_are_we_are_a_test_calendar",
                "name": "We are, we are, a... Test Calendar",
                "track": True,
                "ignore_availability": True,
            }
        ],
    }


async def test_found_calendar(hass, google_setup, mock_next_event, test_calendar):
    """Test when a calendar is found."""
    config = {
        "google": {
            CONF_CLIENT_ID: "id",
            CONF_CLIENT_SECRET: "secret",
            "track_new_calendar": True,
        }
    }
    assert await async_setup_component(hass, "google", config)
    assert hass.data[google.DATA_INDEX] == {}

    await hass.services.async_call(
        "google", google.SERVICE_FOUND_CALENDARS, test_calendar, blocking=True
    )

    assert hass.data[google.DATA_INDEX].get(test_calendar["id"]) is not None
