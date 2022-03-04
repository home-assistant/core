"""The tests for the Google Calendar component."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
import datetime
from typing import Any
from unittest.mock import Mock, call, patch

from oauth2client.client import (
    FlowExchangeError,
    OAuth2Credentials,
    OAuth2DeviceCodeError,
)
import pytest

from homeassistant.components.google import DOMAIN, SERVICE_ADD_EVENT
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant, State
from homeassistant.util.dt import utcnow

from .conftest import (
    CALENDAR_ID,
    TEST_API_ENTITY,
    TEST_API_ENTITY_NAME,
    TEST_YAML_ENTITY,
    TEST_YAML_ENTITY_NAME,
    ApiResult,
    ComponentSetup,
    YieldFixture,
)

from tests.common import async_fire_time_changed

# Typing helpers
HassApi = Callable[[], Awaitable[dict[str, Any]]]

CODE_CHECK_INTERVAL = 1
CODE_CHECK_ALARM_TIMEDELTA = datetime.timedelta(seconds=CODE_CHECK_INTERVAL * 2)


@pytest.fixture
async def code_expiration_delta() -> datetime.timedelta:
    """Fixture for code expiration time, defaulting to the future."""
    return datetime.timedelta(minutes=3)


@pytest.fixture
async def mock_code_flow(
    code_expiration_delta: datetime.timedelta,
) -> YieldFixture[Mock]:
    """Fixture for initiating OAuth flow."""
    with patch(
        "oauth2client.client.OAuth2WebServerFlow.step1_get_device_and_user_codes",
    ) as mock_flow:
        mock_flow.return_value.user_code_expiry = utcnow() + code_expiration_delta
        mock_flow.return_value.interval = CODE_CHECK_INTERVAL
        yield mock_flow


@pytest.fixture
async def mock_exchange(creds: OAuth2Credentials) -> YieldFixture[Mock]:
    """Fixture for mocking out the exchange for credentials."""
    with patch(
        "oauth2client.client.OAuth2WebServerFlow.step2_exchange", return_value=creds
    ) as mock:
        yield mock


@pytest.fixture
async def mock_notification() -> YieldFixture[Mock]:
    """Fixture for capturing persistent notifications."""
    with patch("homeassistant.components.persistent_notification.create") as mock:
        yield mock


async def fire_alarm(hass, point_in_time):
    """Fire an alarm and wait for callbacks to run."""
    with patch("homeassistant.util.dt.utcnow", return_value=point_in_time):
        async_fire_time_changed(hass, point_in_time)
        await hass.async_block_till_done()


@pytest.mark.parametrize("config", [{}])
async def test_setup_config_empty(
    hass: HomeAssistant,
    component_setup: ComponentSetup,
    mock_notification: Mock,
):
    """Test setup component with an empty configuruation."""
    assert await component_setup()

    mock_notification.assert_not_called()

    assert not hass.states.get(TEST_YAML_ENTITY)


def assert_state(actual: State | None, expected: State | None) -> None:
    """Assert that the two states are equal."""
    if actual is None:
        assert actual == expected
        return
    assert actual.entity_id == expected.entity_id
    assert actual.state == expected.state
    assert actual.attributes == expected.attributes


async def test_init_success(
    hass: HomeAssistant,
    mock_code_flow: Mock,
    mock_exchange: Mock,
    mock_notification: Mock,
    mock_calendars_yaml: None,
    component_setup: ComponentSetup,
) -> None:
    """Test successful creds setup."""
    assert await component_setup()

    # Run one tick to invoke the credential exchange check
    now = utcnow()
    await fire_alarm(hass, now + CODE_CHECK_ALARM_TIMEDELTA)

    state = hass.states.get(TEST_YAML_ENTITY)
    assert state
    assert state.name == TEST_YAML_ENTITY_NAME
    assert state.state == STATE_OFF

    mock_notification.assert_called()
    assert "We are all setup now" in mock_notification.call_args[0][1]


async def test_code_error(
    hass: HomeAssistant,
    mock_code_flow: Mock,
    component_setup: ComponentSetup,
    mock_notification: Mock,
) -> None:
    """Test loading the integration with no existing credentials."""

    with patch(
        "oauth2client.client.OAuth2WebServerFlow.step1_get_device_and_user_codes",
        side_effect=OAuth2DeviceCodeError("Test Failure"),
    ):
        assert await component_setup()

    assert not hass.states.get(TEST_YAML_ENTITY)

    mock_notification.assert_called()
    assert "Error: Test Failure" in mock_notification.call_args[0][1]


@pytest.mark.parametrize("code_expiration_delta", [datetime.timedelta(minutes=-5)])
async def test_expired_after_exchange(
    hass: HomeAssistant,
    mock_code_flow: Mock,
    component_setup: ComponentSetup,
    mock_notification: Mock,
) -> None:
    """Test loading the integration with no existing credentials."""

    assert await component_setup()

    now = utcnow()
    await fire_alarm(hass, now + CODE_CHECK_ALARM_TIMEDELTA)

    assert not hass.states.get(TEST_YAML_ENTITY)

    mock_notification.assert_called()
    assert (
        "Authentication code expired, please restart Home-Assistant and try again"
        in mock_notification.call_args[0][1]
    )


async def test_exchange_error(
    hass: HomeAssistant,
    mock_code_flow: Mock,
    component_setup: ComponentSetup,
    mock_notification: Mock,
) -> None:
    """Test an error while exchanging the code for credentials."""

    with patch(
        "oauth2client.client.OAuth2WebServerFlow.step2_exchange",
        side_effect=FlowExchangeError(),
    ):
        assert await component_setup()

        now = utcnow()
        await fire_alarm(hass, now + CODE_CHECK_ALARM_TIMEDELTA)

    assert not hass.states.get(TEST_YAML_ENTITY)

    mock_notification.assert_called()
    assert "In order to authorize Home-Assistant" in mock_notification.call_args[0][1]


async def test_existing_token(
    hass: HomeAssistant,
    mock_token_read: None,
    component_setup: ComponentSetup,
    mock_calendars_yaml: None,
    mock_notification: Mock,
) -> None:
    """Test setup with an existing token file."""
    assert await component_setup()

    state = hass.states.get(TEST_YAML_ENTITY)
    assert state
    assert state.name == TEST_YAML_ENTITY_NAME
    assert state.state == STATE_OFF

    mock_notification.assert_not_called()


@pytest.mark.parametrize(
    "token_scopes", ["https://www.googleapis.com/auth/calendar.readonly"]
)
async def test_existing_token_missing_scope(
    hass: HomeAssistant,
    token_scopes: list[str],
    mock_token_read: None,
    component_setup: ComponentSetup,
    mock_calendars_yaml: None,
    mock_notification: Mock,
    mock_code_flow: Mock,
    mock_exchange: Mock,
) -> None:
    """Test setup where existing token does not have sufficient scopes."""
    assert await component_setup()

    # Run one tick to invoke the credential exchange check
    now = utcnow()
    await fire_alarm(hass, now + CODE_CHECK_ALARM_TIMEDELTA)
    assert len(mock_exchange.mock_calls) == 1

    state = hass.states.get(TEST_YAML_ENTITY)
    assert state
    assert state.name == TEST_YAML_ENTITY_NAME
    assert state.state == STATE_OFF

    # No notifications on success
    mock_notification.assert_called()
    assert "We are all setup now" in mock_notification.call_args[0][1]


@pytest.mark.parametrize("calendars_config", [[{"cal_id": "invalid-schema"}]])
async def test_calendar_yaml_missing_required_fields(
    hass: HomeAssistant,
    mock_token_read: None,
    component_setup: ComponentSetup,
    calendars_config: list[dict[str, Any]],
    mock_calendars_yaml: None,
    mock_notification: Mock,
) -> None:
    """Test setup with a missing schema fields, ignores the error and continues."""
    assert await component_setup()

    assert not hass.states.get(TEST_YAML_ENTITY)

    mock_notification.assert_not_called()


@pytest.mark.parametrize("calendars_config", [[{"missing-cal_id": "invalid-schema"}]])
async def test_invalid_calendar_yaml(
    hass: HomeAssistant,
    mock_token_read: None,
    component_setup: ComponentSetup,
    calendars_config: list[dict[str, Any]],
    mock_calendars_yaml: None,
    mock_notification: Mock,
) -> None:
    """Test setup with missing entity id fields fails to setup the integration."""

    # Integration fails to setup
    assert not await component_setup()

    assert not hass.states.get(TEST_YAML_ENTITY)

    mock_notification.assert_not_called()


@pytest.mark.parametrize(
    "google_config_track_new,calendars_config,expected_state",
    [
        (
            None,
            [],
            State(
                TEST_API_ENTITY,
                STATE_OFF,
                attributes={
                    "offset_reached": False,
                    "friendly_name": TEST_API_ENTITY_NAME,
                },
            ),
        ),
        (
            True,
            [],
            State(
                TEST_API_ENTITY,
                STATE_OFF,
                attributes={
                    "offset_reached": False,
                    "friendly_name": TEST_API_ENTITY_NAME,
                },
            ),
        ),
        (False, [], None),
    ],
    ids=["default", "True", "False"],
)
async def test_track_new(
    hass: HomeAssistant,
    mock_token_read: None,
    component_setup: ComponentSetup,
    mock_calendars_list: ApiResult,
    test_api_calendar: dict[str, Any],
    mock_calendars_yaml: None,
    expected_state: State,
) -> None:
    """Test behavior of configuration.yaml settings for tracking new calendars not in the config."""

    mock_calendars_list({"items": [test_api_calendar]})
    assert await component_setup()

    # The calendar does not
    state = hass.states.get(TEST_API_ENTITY)
    assert_state(state, expected_state)


@pytest.mark.parametrize("calendars_config", [[]])
async def test_found_calendar_from_api(
    hass: HomeAssistant,
    mock_token_read: None,
    component_setup: ComponentSetup,
    mock_calendars_yaml: None,
    mock_calendars_list: ApiResult,
    test_api_calendar: dict[str, Any],
) -> None:
    """Test finding a calendar from the API."""

    mock_calendars_list({"items": [test_api_calendar]})
    assert await component_setup()

    # The calendar does not
    state = hass.states.get(TEST_API_ENTITY)
    assert state
    assert state.name == TEST_API_ENTITY_NAME
    assert state.state == STATE_OFF

    # No yaml config loaded that overwrites the entity name
    assert not hass.states.get(TEST_YAML_ENTITY)


@pytest.mark.parametrize(
    "calendars_config_track,expected_state",
    [
        (
            True,
            State(
                TEST_YAML_ENTITY,
                STATE_OFF,
                attributes={
                    "offset_reached": False,
                    "friendly_name": TEST_YAML_ENTITY_NAME,
                },
            ),
        ),
        (False, None),
    ],
)
async def test_calendar_config_track_new(
    hass: HomeAssistant,
    mock_token_read: None,
    component_setup: ComponentSetup,
    mock_calendars_yaml: None,
    mock_calendars_list: ApiResult,
    test_api_calendar: dict[str, Any],
    calendars_config_track: bool,
    expected_state: State,
) -> None:
    """Test calendar config that overrides whether or not a calendar is tracked."""

    mock_calendars_list({"items": [test_api_calendar]})
    assert await component_setup()

    state = hass.states.get(TEST_YAML_ENTITY)
    assert_state(state, expected_state)
    if calendars_config_track:
        assert state
        assert state.name == TEST_YAML_ENTITY_NAME
        assert state.state == STATE_OFF
    else:
        assert not state


async def test_add_event(
    hass: HomeAssistant,
    mock_token_read: None,
    component_setup: ComponentSetup,
    mock_calendars_list: ApiResult,
    test_api_calendar: dict[str, Any],
    mock_insert_event: Mock,
) -> None:
    """Test service call that adds an event."""

    assert await component_setup()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_EVENT,
        {
            "calendar_id": CALENDAR_ID,
            "summary": "Summary",
            "description": "Description",
        },
        blocking=True,
    )
    mock_insert_event.assert_called()
    assert mock_insert_event.mock_calls[0] == call(
        calendarId=CALENDAR_ID,
        body={
            "summary": "Summary",
            "description": "Description",
            "start": {},
            "end": {},
        },
    )


@pytest.mark.parametrize(
    "date_fields,start_timedelta,end_timedelta",
    [
        (
            {"in": {"days": 3}},
            datetime.timedelta(days=3),
            datetime.timedelta(days=4),
        ),
        (
            {"in": {"weeks": 1}},
            datetime.timedelta(days=7),
            datetime.timedelta(days=8),
        ),
    ],
    ids=["in_days", "in_weeks"],
)
async def test_add_event_date_in_x(
    hass: HomeAssistant,
    mock_token_read: None,
    component_setup: ComponentSetup,
    mock_calendars_list: ApiResult,
    test_api_calendar: dict[str, Any],
    mock_insert_event: Mock,
    date_fields: dict[str, Any],
    start_timedelta: datetime.timedelta,
    end_timedelta: datetime.timedelta,
) -> None:
    """Test service call that adds an event with various time ranges."""

    assert await component_setup()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_EVENT,
        {
            "calendar_id": CALENDAR_ID,
            "summary": "Summary",
            "description": "Description",
            **date_fields,
        },
        blocking=True,
    )
    mock_insert_event.assert_called()

    now = datetime.datetime.now()
    start_date = now + start_timedelta
    end_date = now + end_timedelta

    assert mock_insert_event.mock_calls[0] == call(
        calendarId=CALENDAR_ID,
        body={
            "summary": "Summary",
            "description": "Description",
            "start": {"date": start_date.date().isoformat()},
            "end": {"date": end_date.date().isoformat()},
        },
    )


async def test_add_event_date(
    hass: HomeAssistant,
    mock_token_read: None,
    component_setup: ComponentSetup,
    mock_calendars_list: ApiResult,
    mock_insert_event: Mock,
) -> None:
    """Test service call that sets a date range."""

    assert await component_setup()

    now = utcnow()
    today = now.date()
    end_date = today + datetime.timedelta(days=2)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_EVENT,
        {
            "calendar_id": CALENDAR_ID,
            "summary": "Summary",
            "description": "Description",
            "start_date": today.isoformat(),
            "end_date": end_date.isoformat(),
        },
        blocking=True,
    )
    mock_insert_event.assert_called()

    assert mock_insert_event.mock_calls[0] == call(
        calendarId=CALENDAR_ID,
        body={
            "summary": "Summary",
            "description": "Description",
            "start": {"date": today.isoformat()},
            "end": {"date": end_date.isoformat()},
        },
    )


async def test_add_event_date_time(
    hass: HomeAssistant,
    mock_token_read: None,
    component_setup: ComponentSetup,
    mock_calendars_list: ApiResult,
    test_api_calendar: dict[str, Any],
    mock_insert_event: Mock,
) -> None:
    """Test service call that adds an event with a date time range."""

    assert await component_setup()

    start_datetime = datetime.datetime.now()
    delta = datetime.timedelta(days=3, hours=3)
    end_datetime = start_datetime + delta

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_EVENT,
        {
            "calendar_id": CALENDAR_ID,
            "summary": "Summary",
            "description": "Description",
            "start_date_time": start_datetime.isoformat(),
            "end_date_time": end_datetime.isoformat(),
        },
        blocking=True,
    )
    mock_insert_event.assert_called()

    assert mock_insert_event.mock_calls[0] == call(
        calendarId=CALENDAR_ID,
        body={
            "summary": "Summary",
            "description": "Description",
            "start": {
                "dateTime": start_datetime.isoformat(timespec="seconds"),
                "timeZone": "CST",
            },
            "end": {
                "dateTime": end_datetime.isoformat(timespec="seconds"),
                "timeZone": "CST",
            },
        },
    )
