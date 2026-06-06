"""Tests for init platform of Remote Calendar."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from httpx import HTTPError, InvalidURL, Response, TimeoutException
import pytest
import respx

from homeassistant.components.remote_calendar.const import CONF_CALENDAR_NAME, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    STATE_OFF,
)
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import CALENDAR_NAME, CALENDER_URL, TEST_ENTITY

from tests.common import MockConfigEntry, async_fire_time_changed


@respx.mock
async def test_load_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry, ics_content: str
) -> None:
    """Test loading and unloading a config entry."""
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=200,
            text=ics_content,
        )
    )
    await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == STATE_OFF

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


@respx.mock
async def test_setup_fetches_calendar_once(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    ics_content: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the calendar is downloaded and parsed only once during setup.

    Regression test for https://github.com/home-assistant/core/issues/148315:
    adding the entity must not trigger a second coordinator refresh, which would
    re-download and re-parse the calendar and roughly double the setup time for
    large calendars.
    """
    route = respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=200,
            text=ics_content,
        )
    )
    await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED
    assert route.call_count == 1

    # Flush any debounced refresh a regression could have scheduled while the
    # entity was being added; the calendar must still only have been fetched
    # once.
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert route.call_count == 1


@respx.mock
async def test_raise_for_status(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test update failed using respx to simulate HTTP exceptions."""
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=403,
        )
    )
    await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "side_effect",
    [
        TimeoutException("Connection timed out"),
        HTTPError("Connection failed"),
        InvalidURL("Unsupported protocol"),
        ValueError("Invalid response"),
    ],
)
@respx.mock
async def test_update_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    side_effect: Exception,
) -> None:
    """Test update failed using respx to simulate different exceptions."""
    respx.get(CALENDER_URL).mock(side_effect=side_effect)
    await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@respx.mock
async def test_calendar_parse_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test CalendarParseError using respx."""
    respx.get(CALENDER_URL).mock(
        return_value=Response(status_code=200, text="not a calendar")
    )
    await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@respx.mock
async def test_load_with_auth(hass: HomeAssistant, ics_content: str) -> None:
    """Test loading a config entry with basic auth credentials."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_CALENDAR_NAME: CALENDAR_NAME,
            CONF_URL: CALENDER_URL,
            CONF_VERIFY_SSL: True,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
        },
    )
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=200,
            text=ics_content,
        )
    )
    await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == STATE_OFF
