"""The tests for the Google Calendar component."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import datetime
import http
import time
from typing import Any
from unittest.mock import Mock, patch
import zoneinfo

from aiohttp.client_exceptions import ClientError
import pytest
import voluptuous as vol

from homeassistant.components.google import DOMAIN, SERVICE_ADD_EVENT
from homeassistant.components.google.calendar import SERVICE_CREATE_EVENT
from homeassistant.components.google.const import CONF_CALENDAR_ACCESS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_OFF
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.dt import UTC, utcnow

from .conftest import (
    CALENDAR_ID,
    EMAIL_ADDRESS,
    TEST_API_ENTITY,
    TEST_API_ENTITY_NAME,
    TEST_YAML_ENTITY,
    ApiResult,
    ComponentSetup,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

EXPIRED_TOKEN_TIMESTAMP = datetime.datetime(2022, 4, 8).timestamp()

# Typing helpers
HassApi = Callable[[], Awaitable[dict[str, Any]]]

TEST_EVENT_SUMMARY = "Test Summary"
TEST_EVENT_DESCRIPTION = "Test Description"
TEST_EVENT_LOCATION = "Test Location"


def assert_state(actual: State | None, expected: State | None) -> None:
    """Assert that the two states are equal."""
    if actual is None or expected is None:
        assert actual == expected
        return
    assert actual.entity_id == expected.entity_id
    assert actual.state == expected.state
    assert actual.attributes == expected.attributes


@pytest.fixture(
    params=[
        (
            DOMAIN,
            SERVICE_ADD_EVENT,
            {"calendar_id": CALENDAR_ID},
            None,
        ),
        (
            DOMAIN,
            SERVICE_CREATE_EVENT,
            {},
            {"entity_id": TEST_API_ENTITY},
        ),
        (
            "calendar",
            SERVICE_CREATE_EVENT,
            {},
            {"entity_id": TEST_API_ENTITY},
        ),
    ],
    ids=("google.add_event", "google.create_event", "calendar.create_event"),
)
def add_event_call_service(
    hass: HomeAssistant,
    request: Any,
) -> Callable[dict[str, Any], Awaitable[None]]:
    """Fixture for calling the add or create event service."""
    (domain, service_call, data, target) = request.param

    async def call_service(params: dict[str, Any]) -> None:
        await hass.services.async_call(
            domain,
            service_call,
            {
                **data,
                **params,
                "summary": TEST_EVENT_SUMMARY,
                "description": TEST_EVENT_DESCRIPTION,
            },
            target=target,
            blocking=True,
        )

    return call_service


async def test_unload_entry(
    hass: HomeAssistant,
    component_setup: ComponentSetup,
) -> None:
    """Test load and unload of a ConfigEntry."""
    await component_setup()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "token_scopes", ["https://www.googleapis.com/auth/calendar.readonly"]
)
async def test_existing_token_missing_scope(
    hass: HomeAssistant,
    token_scopes: list[str],
    component_setup: ComponentSetup,
    config_entry: MockConfigEntry,
) -> None:
    """Test setup where existing token does not have sufficient scopes."""
    await component_setup()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


@pytest.mark.parametrize("config_entry_options", [{CONF_CALENDAR_ACCESS: "read_only"}])
async def test_config_entry_scope_reauth(
    hass: HomeAssistant,
    token_scopes: list[str],
    component_setup: ComponentSetup,
    config_entry: MockConfigEntry,
) -> None:
    """Test setup where the config entry options requires reauth to match the scope."""
    await component_setup()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


@pytest.mark.parametrize("calendars_config", [[{"cal_id": "invalid-schema"}]])
async def test_calendar_yaml_missing_required_fields(
    hass: HomeAssistant,
    component_setup: ComponentSetup,
    calendars_config: list[dict[str, Any]],
    mock_calendars_yaml: None,
    config_entry: MockConfigEntry,
) -> None:
    """Test setup with a missing schema fields, ignores the error and continues."""
    assert not await component_setup()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize("calendars_config", [[{"missing-cal_id": "invalid-schema"}]])
async def test_invalid_calendar_yaml(
    hass: HomeAssistant,
    component_setup: ComponentSetup,
    calendars_config: list[dict[str, Any]],
    mock_calendars_yaml: None,
    config_entry: MockConfigEntry,
) -> None:
    """Test setup with missing entity id fields fails to load the platform."""
    assert not await component_setup()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_calendar_yaml_error(
    hass: HomeAssistant,
    component_setup: ComponentSetup,
    mock_calendars_list: ApiResult,
    test_api_calendar: dict[str, Any],
    mock_events_list: ApiResult,
) -> None:
    """Test setup with yaml file not found."""
    mock_calendars_list({"items": [test_api_calendar]})
    mock_events_list({})

    with patch("homeassistant.components.google.open", side_effect=FileNotFoundError()):
        assert await component_setup()

    assert not hass.states.get(TEST_YAML_ENTITY)
    assert hass.states.get(TEST_API_ENTITY)


@pytest.mark.parametrize("calendars_config", [None])
async def test_empty_calendar_yaml(
    hass: HomeAssistant,
    component_setup: ComponentSetup,
    calendars_config: list[dict[str, Any]],
    mock_calendars_yaml: None,
    mock_calendars_list: ApiResult,
    test_api_calendar: dict[str, Any],
    mock_events_list: ApiResult,
) -> None:
    """Test an empty yaml file is equivalent to a missing yaml file."""
    mock_calendars_list({"items": [test_api_calendar]})
    mock_events_list({})

    assert await component_setup()

    assert not hass.states.get(TEST_YAML_ENTITY)
    assert hass.states.get(TEST_API_ENTITY)


async def test_init_calendar(
    hass: HomeAssistant,
    component_setup: ComponentSetup,
    mock_calendars_list: ApiResult,
    test_api_calendar: dict[str, Any],
    mock_events_list: ApiResult,
) -> None:
    """Test finding a calendar from the API."""

    mock_calendars_list({"items": [test_api_calendar]})
    mock_events_list({})
    assert await component_setup()

    state = hass.states.get(TEST_API_ENTITY)
    assert state
    assert state.name == TEST_API_ENTITY_NAME
    assert state.state == STATE_OFF

    # No yaml config loaded that overwrites the entity name
    assert not hass.states.get(TEST_YAML_ENTITY)


async def test_multiple_config_entries(
    hass: HomeAssistant,
    component_setup: ComponentSetup,
    mock_calendars_list: ApiResult,
    test_api_calendar: dict[str, Any],
    mock_events_list: ApiResult,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test finding a calendar from the API."""

    assert await component_setup()

    config_entry1 = MockConfigEntry(
        domain=DOMAIN, data=config_entry.data, unique_id=EMAIL_ADDRESS
    )
    calendar1 = {
        **test_api_calendar,
        "id": "calendar-id1",
        "summary": "Example Calendar 1",
    }

    mock_calendars_list({"items": [calendar1]})
    mock_events_list({}, calendar_id="calendar-id1")
    config_entry1.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry1.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("calendar.example_calendar_1")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Example calendar 1"

    config_entry2 = MockConfigEntry(
        domain=DOMAIN, data=config_entry.data, unique_id="other-address@example.com"
    )
    calendar2 = {
        **test_api_calendar,
        "id": "calendar-id2",
        "summary": "Example Calendar 2",
    }
    aioclient_mock.clear_requests()
    mock_calendars_list({"items": [calendar2]})
    mock_events_list({}, calendar_id="calendar-id2")
    config_entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("calendar.example_calendar_2")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Example calendar 2"


@pytest.mark.parametrize(
    ("date_fields", "expected_error", "error_match"),
    [
        (
            {},
            vol.error.MultipleInvalid,
            "must contain at least one of start_date, start_date_time, in",
        ),
        (
            {
                "start_date": "2022-04-01",
            },
            vol.error.MultipleInvalid,
            "Start and end dates must both be specified",
        ),
        (
            {
                "end_date": "2022-04-02",
            },
            vol.error.MultipleInvalid,
            "must contain at least one of start_date, start_date_time, in.",
        ),
        (
            {
                "start_date_time": "2022-04-01T06:00:00",
            },
            vol.error.MultipleInvalid,
            "Start and end datetimes must both be specified",
        ),
        (
            {
                "end_date_time": "2022-04-02T07:00:00",
            },
            vol.error.MultipleInvalid,
            "must contain at least one of start_date, start_date_time, in.",
        ),
        (
            {
                "start_date": "2022-04-01",
                "start_date_time": "2022-04-01T06:00:00",
                "end_date_time": "2022-04-02T07:00:00",
            },
            vol.error.MultipleInvalid,
            "must contain at most one of start_date, start_date_time, in.",
        ),
        (
            {
                "start_date_time": "2022-04-01T06:00:00",
                "end_date_time": "2022-04-01T07:00:00",
                "end_date": "2022-04-02",
            },
            vol.error.MultipleInvalid,
            "Start and end dates must both be specified",
        ),
        (
            {
                "start_date": "2022-04-01",
                "end_date_time": "2022-04-02T07:00:00",
            },
            vol.error.MultipleInvalid,
            "Start and end dates must both be specified",
        ),
        (
            {
                "start_date_time": "2022-04-01T07:00:00",
                "end_date": "2022-04-02",
            },
            vol.error.MultipleInvalid,
            "Start and end dates must both be specified",
        ),
        (
            {
                "in": {
                    "days": 2,
                    "weeks": 2,
                }
            },
            vol.error.MultipleInvalid,
            "two or more values in the same group of exclusion 'event_types'",
        ),
        (
            {
                "start_date": "2022-04-01",
                "end_date": "2022-04-02",
                "in": {
                    "days": 2,
                },
            },
            vol.error.MultipleInvalid,
            "must contain at most one of start_date, start_date_time, in.",
        ),
        (
            {
                "start_date_time": "2022-04-01T07:00:00",
                "end_date_time": "2022-04-01T07:00:00",
                "in": {
                    "days": 2,
                },
            },
            vol.error.MultipleInvalid,
            "must contain at most one of start_date, start_date_time, in.",
        ),
    ],
    ids=[
        "missing_all",
        "missing_end_date",
        "missing_start_date",
        "missing_end_datetime",
        "missing_start_datetime",
        "multiple_start",
        "multiple_end",
        "missing_end_date",
        "missing_end_date_time",
        "multiple_in",
        "unexpected_in_with_date",
        "unexpected_in_with_datetime",
    ],
)
async def test_add_event_invalid_params(
    hass: HomeAssistant,
    component_setup: ComponentSetup,
    mock_calendars_list: ApiResult,
    test_api_calendar: dict[str, Any],
    mock_events_list: ApiResult,
    add_event_call_service: Callable[dict[str, Any], Awaitable[None]],
    date_fields: dict[str, Any],
    expected_error: type[Exception],
    error_match: str | None,
) -> None:
    """Test service calls with incorrect fields."""

    mock_calendars_list({"items": [test_api_calendar]})
    mock_events_list({})
    assert await component_setup()

    with pytest.raises(expected_error, match=error_match):
        await add_event_call_service(date_fields)


@pytest.mark.parametrize(
    ("date_fields", "start_timedelta", "end_timedelta"),
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
    component_setup: ComponentSetup,
    mock_calendars_list: ApiResult,
    mock_insert_event: Callable[[..., dict[str, Any]], None],
    test_api_calendar: dict[str, Any],
    mock_events_list: ApiResult,
    date_fields: dict[str, Any],
    start_timedelta: datetime.timedelta,
    end_timedelta: datetime.timedelta,
    aioclient_mock: AiohttpClientMocker,
    add_event_call_service: Callable[dict[str, Any], Awaitable[None]],
) -> None:
    """Test service call that adds an event with various time ranges."""

    mock_calendars_list({"items": [test_api_calendar]})
    mock_events_list({})
    assert await component_setup()

    now = datetime.datetime.now()
    start_date = now + start_timedelta
    end_date = now + end_timedelta

    aioclient_mock.clear_requests()
    mock_insert_event(
        calendar_id=CALENDAR_ID,
    )

    await add_event_call_service(date_fields)
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2] == {
        "summary": TEST_EVENT_SUMMARY,
        "description": TEST_EVENT_DESCRIPTION,
        "start": {"date": start_date.date().isoformat()},
        "end": {"date": end_date.date().isoformat()},
    }


async def test_add_event_date(
    hass: HomeAssistant,
    component_setup: ComponentSetup,
    mock_calendars_list: ApiResult,
    test_api_calendar: dict[str, Any],
    mock_insert_event: Callable[[str, dict[str, Any]], None],
    mock_events_list: ApiResult,
    aioclient_mock: AiohttpClientMocker,
    add_event_call_service: Callable[dict[str, Any], Awaitable[None]],
) -> None:
    """Test service call that sets a date range."""

    mock_calendars_list({"items": [test_api_calendar]})
    mock_events_list({})
    assert await component_setup()

    now = utcnow()
    today = now.date()
    end_date = today + datetime.timedelta(days=2)

    aioclient_mock.clear_requests()
    mock_insert_event(
        calendar_id=CALENDAR_ID,
    )

    await add_event_call_service(
        {
            "start_date": today.isoformat(),
            "end_date": end_date.isoformat(),
        },
    )
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2] == {
        "summary": TEST_EVENT_SUMMARY,
        "description": TEST_EVENT_DESCRIPTION,
        "start": {"date": today.isoformat()},
        "end": {"date": end_date.isoformat()},
    }


async def test_add_event_date_time(
    hass: HomeAssistant,
    component_setup: ComponentSetup,
    mock_calendars_list: ApiResult,
    mock_insert_event: Callable[[str, dict[str, Any]], None],
    test_api_calendar: dict[str, Any],
    mock_events_list: ApiResult,
    aioclient_mock: AiohttpClientMocker,
    add_event_call_service: Callable[dict[str, Any], Awaitable[None]],
) -> None:
    """Test service call that adds an event with a date time range."""

    mock_calendars_list({"items": [test_api_calendar]})
    mock_events_list({})
    assert await component_setup()

    start_datetime = datetime.datetime.now(tz=zoneinfo.ZoneInfo("America/Regina"))
    delta = datetime.timedelta(days=3, hours=3)
    end_datetime = start_datetime + delta

    aioclient_mock.clear_requests()
    mock_insert_event(
        calendar_id=CALENDAR_ID,
    )

    await add_event_call_service(
        {
            "start_date_time": start_datetime.isoformat(),
            "end_date_time": end_datetime.isoformat(),
        },
    )
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2] == {
        "summary": TEST_EVENT_SUMMARY,
        "description": TEST_EVENT_DESCRIPTION,
        "start": {
            "dateTime": start_datetime.isoformat(timespec="seconds"),
            "timeZone": "America/Regina",
        },
        "end": {
            "dateTime": end_datetime.isoformat(timespec="seconds"),
            "timeZone": "America/Regina",
        },
    }


@pytest.mark.parametrize(
    "calendars_config",
    [
        [
            {
                "cal_id": CALENDAR_ID,
                "entities": [
                    {
                        "device_id": "backyard_light",
                        "name": "Backyard Light",
                        "search": "#Backyard",
                    },
                ],
            }
        ],
    ],
)
async def test_unsupported_create_event(
    hass: HomeAssistant,
    mock_calendars_yaml: Mock,
    component_setup: ComponentSetup,
    mock_calendars_list: ApiResult,
    mock_insert_event: Callable[[str, dict[str, Any]], None],
    test_api_calendar: dict[str, Any],
    mock_events_list: ApiResult,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test create event service call is unsupported for virtual calendars."""

    mock_calendars_list({"items": [test_api_calendar]})
    mock_events_list({})
    assert await component_setup()

    start_datetime = datetime.datetime.now(tz=zoneinfo.ZoneInfo("America/Regina"))
    delta = datetime.timedelta(days=3, hours=3)
    end_datetime = start_datetime + delta

    with pytest.raises(HomeAssistantError, match="does not support this service"):
        await hass.services.async_call(
            DOMAIN,
            "create_event",
            {
                # **data,
                "start_date_time": start_datetime.isoformat(),
                "end_date_time": end_datetime.isoformat(),
                "summary": TEST_EVENT_SUMMARY,
                "description": TEST_EVENT_DESCRIPTION,
            },
            target={"entity_id": "calendar.backyard_light"},
            blocking=True,
        )


async def test_add_event_failure(
    hass: HomeAssistant,
    component_setup: ComponentSetup,
    mock_calendars_list: ApiResult,
    test_api_calendar: dict[str, Any],
    mock_events_list: ApiResult,
    mock_insert_event: Callable[[..., dict[str, Any]], None],
    add_event_call_service: Callable[dict[str, Any], Awaitable[None]],
) -> None:
    """Test service calls with incorrect fields."""

    mock_calendars_list({"items": [test_api_calendar]})
    mock_events_list({})
    assert await component_setup()

    mock_insert_event(
        calendar_id=CALENDAR_ID,
        exc=ClientError(),
    )

    with pytest.raises(HomeAssistantError):
        await add_event_call_service(
            {"start_date": "2022-05-01", "end_date": "2022-05-02"}
        )


async def test_add_event_location(
    hass: HomeAssistant,
    component_setup: ComponentSetup,
    mock_calendars_list: ApiResult,
    test_api_calendar: dict[str, Any],
    mock_insert_event: Callable[[str, dict[str, Any]], None],
    mock_events_list: ApiResult,
    aioclient_mock: AiohttpClientMocker,
    add_event_call_service: Callable[dict[str, Any], Awaitable[None]],
) -> None:
    """Test service call that sets a location field."""

    mock_calendars_list({"items": [test_api_calendar]})
    mock_events_list({})
    assert await component_setup()

    now = utcnow()
    today = now.date()
    end_date = today + datetime.timedelta(days=2)

    aioclient_mock.clear_requests()
    mock_insert_event(
        calendar_id=CALENDAR_ID,
    )

    await add_event_call_service(
        {
            "start_date": today.isoformat(),
            "end_date": end_date.isoformat(),
            "location": TEST_EVENT_LOCATION,
        },
    )
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2] == {
        "summary": TEST_EVENT_SUMMARY,
        "description": TEST_EVENT_DESCRIPTION,
        "location": TEST_EVENT_LOCATION,
        "start": {"date": today.isoformat()},
        "end": {"date": end_date.isoformat()},
    }


@pytest.mark.parametrize(
    "config_entry_token_expiry",
    [
        (datetime.datetime.max.replace(tzinfo=UTC).timestamp() + 1),
        (utcnow().replace(tzinfo=None).timestamp()),
    ],
    ids=["max_timestamp", "timestamp_naive"],
)
async def test_invalid_token_expiry_in_config_entry(
    hass: HomeAssistant,
    component_setup: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Exercise case in issue #69623 with invalid token expiration persisted."""

    # The token is refreshed and new expiration values are returned
    expires_in = 86400
    expires_at = time.time() + expires_in
    aioclient_mock.post(
        "https://oauth2.googleapis.com/token",
        json={
            "refresh_token": "some-refresh-token",
            "access_token": "some-updated-token",
            "expires_at": expires_at,
            "expires_in": expires_in,
        },
    )

    assert await component_setup()

    # Verify token expiration values are updated
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    assert entries[0].data["token"]["access_token"] == "some-updated-token"
    assert entries[0].data["token"]["expires_in"] == expires_in


@pytest.mark.parametrize("config_entry_token_expiry", [EXPIRED_TOKEN_TIMESTAMP])
async def test_expired_token_refresh_internal_error(
    hass: HomeAssistant,
    component_setup: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Generic errors on reauth are treated as a retryable setup error."""

    aioclient_mock.post(
        "https://oauth2.googleapis.com/token",
        status=http.HTTPStatus.INTERNAL_SERVER_ERROR,
    )

    await component_setup()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "config_entry_token_expiry",
    [EXPIRED_TOKEN_TIMESTAMP],
)
async def test_expired_token_requires_reauth(
    hass: HomeAssistant,
    component_setup: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test case where reauth is required for token that cannot be refreshed."""

    aioclient_mock.post(
        "https://oauth2.googleapis.com/token",
        status=http.HTTPStatus.BAD_REQUEST,
    )

    await component_setup()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


@pytest.mark.parametrize(
    ("calendars_config", "expect_write_calls"),
    [
        (
            [
                {
                    "cal_id": "ignored",
                    "entities": {"device_id": "existing", "name": "existing"},
                }
            ],
            True,
        ),
        ([], False),
    ],
    ids=["has_yaml", "no_yaml"],
)
async def test_calendar_yaml_update(
    hass: HomeAssistant,
    component_setup: ComponentSetup,
    mock_calendars_yaml: Mock,
    mock_calendars_list: ApiResult,
    test_api_calendar: dict[str, Any],
    mock_events_list: ApiResult,
    calendars_config: dict[str, Any],
    expect_write_calls: bool,
) -> None:
    """Test updating the yaml file with a new calendar."""

    mock_calendars_list({"items": [test_api_calendar]})
    mock_events_list({})
    assert await component_setup()

    mock_calendars_yaml().read.assert_called()
    assert mock_calendars_yaml().write.called is expect_write_calls

    state = hass.states.get(TEST_API_ENTITY)
    assert state
    assert state.name == TEST_API_ENTITY_NAME
    assert state.state == STATE_OFF

    # No yaml config loaded that overwrites the entity name
    assert not hass.states.get(TEST_YAML_ENTITY)


async def test_update_will_reload(
    hass: HomeAssistant,
    component_setup: ComponentSetup,
    mock_calendars_list: ApiResult,
    test_api_calendar: dict[str, Any],
    mock_events_list: ApiResult,
    config_entry: MockConfigEntry,
) -> None:
    """Test updating config entry options will trigger a reload."""
    mock_calendars_list({"items": [test_api_calendar]})
    mock_events_list({})
    await component_setup()
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.options == {}  # read_write is default

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload",
        return_value=None,
    ) as mock_reload:
        # No-op does not reload
        hass.config_entries.async_update_entry(
            config_entry, options={CONF_CALENDAR_ACCESS: "read_write"}
        )
        await hass.async_block_till_done()
        mock_reload.assert_not_called()

        # Data change does not trigger reload
        hass.config_entries.async_update_entry(
            config_entry,
            data={
                **config_entry.data,
                "example": "field",
            },
        )
        await hass.async_block_till_done()
        mock_reload.assert_not_called()

        # Reload when options changed
        hass.config_entries.async_update_entry(
            config_entry, options={CONF_CALENDAR_ACCESS: "read_only"}
        )
        await hass.async_block_till_done()
        mock_reload.assert_called_once()


@pytest.mark.parametrize("config_entry_unique_id", [None])
async def test_assign_unique_id(
    hass: HomeAssistant,
    component_setup: ComponentSetup,
    mock_calendars_list: ApiResult,
    test_api_calendar: dict[str, Any],
    mock_events_list: ApiResult,
    mock_calendar_get: Callable[[...], None],
    config_entry: MockConfigEntry,
) -> None:
    """Test an existing config is updated to have unique id if it does not exist."""

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert config_entry.unique_id is None

    mock_calendar_get(
        "primary",
        {"id": EMAIL_ADDRESS, "summary": "Personal", "accessRole": "owner"},
    )

    mock_calendars_list({"items": [test_api_calendar]})
    mock_events_list({})
    assert await component_setup()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.unique_id == EMAIL_ADDRESS


@pytest.mark.parametrize(
    ("config_entry_unique_id", "request_status", "config_entry_status"),
    [
        (None, http.HTTPStatus.BAD_REQUEST, ConfigEntryState.SETUP_RETRY),
        (
            None,
            http.HTTPStatus.UNAUTHORIZED,
            ConfigEntryState.SETUP_ERROR,
        ),
    ],
)
async def test_assign_unique_id_failure(
    hass: HomeAssistant,
    component_setup: ComponentSetup,
    mock_calendars_list: ApiResult,
    test_api_calendar: dict[str, Any],
    config_entry: MockConfigEntry,
    mock_events_list: ApiResult,
    mock_calendar_get: Callable[[...], None],
    request_status: http.HTTPStatus,
    config_entry_status: ConfigEntryState,
) -> None:
    """Test lookup failures during unique id assignment are handled gracefully."""

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert config_entry.unique_id is None

    mock_calendar_get(
        "primary",
        {},
        status=request_status,
    )

    mock_calendars_list({"items": [test_api_calendar]})
    mock_events_list({})
    await component_setup()

    assert config_entry.state is config_entry_status
    assert config_entry.unique_id is None


async def test_remove_entry(
    hass: HomeAssistant,
    mock_calendars_list: ApiResult,
    component_setup: ComponentSetup,
    test_api_calendar: dict[str, Any],
    mock_events_list: ApiResult,
) -> None:
    """Test load and remove of a ConfigEntry."""
    mock_calendars_list({"items": [test_api_calendar]})
    mock_events_list({})
    assert await component_setup()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_remove(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
