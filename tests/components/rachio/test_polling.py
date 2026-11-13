"""Tests for the optional polling of Rachio controllers."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from requests.exceptions import ConnectionError as RequestsConnectionError, Timeout

from homeassistant.components.rachio.const import (
    CONF_MANUAL_RUN_MINS,
    CONF_POLL_ENABLED,
    CONF_POLLING,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import (
    CONF_API_KEY,
    CONF_WEBHOOK_ID,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

CONTROLLER_ID = "controller-id"
ZONE_ID = "zone-id"
SCHEDULE_ID = "schedule-id"
ZONE_ENTITY_ID = "switch.test_controller_test_zone"
SCHEDULE_ENTITY_ID = "switch.test_controller_test_schedule"

MOCK_CONTROLLER = {
    "id": CONTROLLER_ID,
    "name": "Test Controller",
    "serialNumber": "serial-number",
    "macAddress": "00:9D:6B:00:00:01",
    "model": "GENERATION3",
    "zones": [{"id": ZONE_ID, "name": "Test Zone", "zoneNumber": 1, "enabled": True}],
    "scheduleRules": [
        {
            "id": SCHEDULE_ID,
            "name": "Test",
            "enabled": True,
            "totalDuration": 600,
            "summary": "Test schedule",
        }
    ],
    "flexScheduleRules": [],
}

POLLING_OPTIONS = {CONF_POLLING: {CONF_POLL_ENABLED: True}}

pytestmark = [
    pytest.mark.parametrize("mock_rachio", [[MOCK_CONTROLLER]], indirect=True),
    pytest.mark.parametrize("init_integration", [Platform.SWITCH], indirect=True),
]


@pytest.fixture
def mock_config_entry(request: pytest.FixtureRequest) -> MockConfigEntry:
    """Return a config entry with the options given by the test."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-api-key", CONF_WEBHOOK_ID: "rachio-test-webhook-id"},
        options=getattr(request, "param", {}),
        unique_id="test-user-id",
    )


def _running() -> tuple[dict, dict[str, Any]]:
    """Return a current_schedule response for a zone and schedule that is running."""
    return ({"status": 200}, {"zoneId": ZONE_ID, "scheduleId": SCHEDULE_ID})


async def _advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    """Advance time and let scheduled updates run."""
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.parametrize("mock_config_entry", [POLLING_OPTIONS], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_polling_updates_state(
    hass: HomeAssistant, mock_rachio: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test zone and schedule state follows what the controller reports."""
    mock_rachio.device.current_schedule.assert_called_once_with(CONTROLLER_ID)
    assert hass.states.is_state(ZONE_ENTITY_ID, STATE_OFF)
    assert hass.states.is_state(SCHEDULE_ENTITY_ID, STATE_OFF)

    mock_rachio.device.current_schedule.return_value = _running()
    await _advance(hass, freezer, timedelta(minutes=1))

    assert hass.states.is_state(ZONE_ENTITY_ID, STATE_ON)
    assert hass.states.is_state(SCHEDULE_ENTITY_ID, STATE_ON)

    mock_rachio.device.current_schedule.return_value = ({"status": 200}, {})
    await _advance(hass, freezer, timedelta(minutes=1))

    assert hass.states.is_state(ZONE_ENTITY_ID, STATE_OFF)
    assert hass.states.is_state(SCHEDULE_ENTITY_ID, STATE_OFF)


@pytest.mark.usefixtures("init_integration")
async def test_polling_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rachio: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test controllers are not polled unless the option is enabled."""
    assert mock_config_entry.runtime_data.controllers[0].poll_coordinator is None
    calls = mock_rachio.device.current_schedule.call_count

    mock_rachio.device.current_schedule.return_value = _running()
    await _advance(hass, freezer, timedelta(hours=1))

    assert mock_rachio.device.current_schedule.call_count == calls
    assert hass.states.is_state(ZONE_ENTITY_ID, STATE_OFF)


@pytest.mark.parametrize("mock_config_entry", [POLLING_OPTIONS], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_poll_error_keeps_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rachio: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed poll does not change state and recovers on the next poll."""
    coordinator = mock_config_entry.runtime_data.controllers[0].poll_coordinator
    mock_rachio.device.current_schedule.return_value = _running()
    await _advance(hass, freezer, timedelta(minutes=1))
    assert hass.states.is_state(ZONE_ENTITY_ID, STATE_ON)

    mock_rachio.device.current_schedule.return_value = ({"status": 429}, {})
    await _advance(hass, freezer, timedelta(minutes=1))
    assert not coordinator.last_update_success
    assert hass.states.is_state(ZONE_ENTITY_ID, STATE_ON)

    mock_rachio.device.current_schedule.return_value = ({"status": 200}, {})
    await _advance(hass, freezer, timedelta(minutes=1))
    assert coordinator.last_update_success
    assert hass.states.is_state(ZONE_ENTITY_ID, STATE_OFF)


@pytest.mark.parametrize("mock_config_entry", [POLLING_OPTIONS], indirect=True)
@pytest.mark.parametrize("error", [Timeout, RequestsConnectionError])
@pytest.mark.usefixtures("init_integration")
async def test_poll_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rachio: MagicMock,
    freezer: FrozenDateTimeFactory,
    error: type[Exception],
) -> None:
    """Test a poll that cannot reach Rachio is reported as a failed update."""
    coordinator = mock_config_entry.runtime_data.controllers[0].poll_coordinator
    mock_rachio.device.current_schedule.side_effect = error

    await _advance(hass, freezer, timedelta(minutes=1))

    assert not coordinator.last_update_success
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert coordinator.last_exception.translation_key == "cannot_connect"


@pytest.mark.parametrize("mock_config_entry", [POLLING_OPTIONS], indirect=True)
@pytest.mark.parametrize("status", [401, 403])
@pytest.mark.usefixtures("init_integration")
async def test_poll_auth_failure_starts_reauth(
    hass: HomeAssistant,
    mock_rachio: MagicMock,
    freezer: FrozenDateTimeFactory,
    status: int,
) -> None:
    """Test a rejected API key during polling starts reauthentication."""
    mock_rachio.device.current_schedule.return_value = ({"status": status}, {})

    await _advance(hass, freezer, timedelta(minutes=1))

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


@pytest.mark.parametrize("mock_config_entry", [POLLING_OPTIONS], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_poll_interval_is_the_computed_minimum(
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test controllers are polled at the shortest interval the account allows."""
    coordinator = mock_config_entry.runtime_data.controllers[0].poll_coordinator
    assert coordinator.update_interval == timedelta(minutes=1)


@pytest.mark.parametrize("mock_config_entry", [POLLING_OPTIONS], indirect=True)
@pytest.mark.parametrize(
    "rate_limit_headers", [{"x-ratelimit-limit": "100"}], indirect=True
)
@pytest.mark.usefixtures("rate_limit_headers", "init_integration")
async def test_no_polling_when_no_interval_fits_the_limit(
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test controllers are not polled if even the longest interval is too often."""
    assert mock_config_entry.runtime_data.controllers[0].poll_coordinator is None


@pytest.mark.parametrize("mock_config_entry", [POLLING_OPTIONS], indirect=True)
@pytest.mark.parametrize(
    "reset_suffix",
    [
        pytest.param("Z", id="utc"),
        pytest.param("Z[UTC]", id="utc-with-zone-name"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_polling_pauses_when_few_calls_remain(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rachio: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    reset_suffix: str,
) -> None:
    """Test polling stops, says so in the log, and resumes after the limit resets."""
    coordinator = mock_config_entry.runtime_data.controllers[0].poll_coordinator
    reset = dt_util.utcnow() + timedelta(hours=2)
    headers = {
        "status": 200,
        "x-ratelimit-remaining": "10",
        "x-ratelimit-reset": reset.strftime("%Y-%m-%dT%H:%M:%S") + reset_suffix,
    }
    mock_rachio.device.current_schedule.return_value = (headers, _running()[1])
    await _advance(hass, freezer, timedelta(minutes=1))
    assert hass.states.is_state(ZONE_ENTITY_ID, STATE_ON)
    calls = mock_rachio.device.current_schedule.call_count

    await _advance(hass, freezer, timedelta(minutes=1))
    await _advance(hass, freezer, timedelta(minutes=1))

    assert mock_rachio.device.current_schedule.call_count == calls
    assert not coordinator.last_update_success
    assert "Only 10 Rachio API calls are left for today" in caplog.text
    assert "shared with the Rachio app" in caplog.text

    mock_rachio.device.current_schedule.return_value = (
        {**headers, "x-ratelimit-remaining": "3500"},
        {},
    )
    await _advance(hass, freezer, timedelta(hours=2))

    assert mock_rachio.device.current_schedule.call_count == calls + 1
    assert coordinator.last_update_success
    assert hass.states.is_state(ZONE_ENTITY_ID, STATE_OFF)


@pytest.mark.parametrize("mock_config_entry", [POLLING_OPTIONS], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_polling_reserves_calls_for_hose_timers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rachio: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test polling pauses early enough to leave calls for the hose timers."""
    coordinator = mock_config_entry.runtime_data.controllers[0].poll_coordinator
    reset = dt_util.utcnow() + timedelta(hours=2)
    mock_rachio.device.current_schedule.return_value = (
        {
            "status": 200,
            "x-ratelimit-remaining": "100",
            "x-ratelimit-reset": reset.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        {},
    )
    await _advance(hass, freezer, timedelta(minutes=1))
    calls = mock_rachio.device.current_schedule.call_count

    await _advance(hass, freezer, timedelta(minutes=1))

    assert mock_rachio.device.current_schedule.call_count == calls
    assert not coordinator.last_update_success


@pytest.mark.parametrize("mock_config_entry", [POLLING_OPTIONS], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_polling_pauses_after_the_limit_is_exhausted(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rachio: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a rejected request still pauses polling until the limit resets."""
    coordinator = mock_config_entry.runtime_data.controllers[0].poll_coordinator
    reset = dt_util.utcnow() + timedelta(hours=2)
    mock_rachio.device.current_schedule.return_value = (
        {
            "status": 429,
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": reset.isoformat(),
        },
        {},
    )
    await _advance(hass, freezer, timedelta(minutes=1))
    assert not coordinator.last_update_success
    assert coordinator.last_exception.retry_after == pytest.approx(7200 - 60)
    calls = mock_rachio.device.current_schedule.call_count

    await _advance(hass, freezer, timedelta(minutes=1))
    await _advance(hass, freezer, timedelta(minutes=1))

    assert mock_rachio.device.current_schedule.call_count == calls


@pytest.mark.parametrize("mock_config_entry", [POLLING_OPTIONS], indirect=True)
@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({"x-ratelimit-remaining": "3000"}, id="plenty-remaining"),
        pytest.param({"x-ratelimit-remaining": "10"}, id="no-reset-time"),
        pytest.param({"x-ratelimit-remaining": "lots"}, id="invalid-count"),
        pytest.param({}, id="no-headers"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_polling_continues_when_not_running_out(
    hass: HomeAssistant,
    mock_rachio: MagicMock,
    freezer: FrozenDateTimeFactory,
    headers: dict[str, str],
) -> None:
    """Test polling carries on unless the headers show calls running out."""
    mock_rachio.device.current_schedule.return_value = ({"status": 200, **headers}, {})
    calls = mock_rachio.device.current_schedule.call_count

    await _advance(hass, freezer, timedelta(minutes=1))
    await _advance(hass, freezer, timedelta(minutes=1))

    assert mock_rachio.device.current_schedule.call_count == calls + 2


@pytest.fixture
def rate_limit_headers(request: pytest.FixtureRequest, mock_rachio: MagicMock) -> None:
    """Return the given headers with the user info response."""
    mock_rachio.person.info.return_value = (
        {"status": 200, **request.param},
        {"id": "test-user-id"},
    )


@pytest.mark.parametrize(
    ("rate_limit_headers", "expected"),
    [
        pytest.param({"x-ratelimit-limit": "1700"}, 1700, id="header"),
        pytest.param({}, 3500, id="missing"),
        pytest.param({"x-ratelimit-limit": "unlimited"}, 3500, id="invalid"),
    ],
    indirect=["rate_limit_headers"],
)
@pytest.mark.usefixtures("rate_limit_headers", "init_integration")
async def test_rate_limit_from_api(
    mock_config_entry: MockConfigEntry, expected: int
) -> None:
    """Test the daily API call limit is read from the response headers."""
    assert mock_config_entry.runtime_data.rate_limit == expected


@pytest.mark.usefixtures("init_integration")
async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the options flow saves the polling options."""
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["description_placeholders"]["daily_limit"] == "3,500"
    assert result["description_placeholders"]["interval"] == "1"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_MANUAL_RUN_MINS: 5, CONF_POLLING: {CONF_POLL_ENABLED: True}},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {
        CONF_MANUAL_RUN_MINS: 5,
        CONF_POLLING: {CONF_POLL_ENABLED: True},
    }


@pytest.mark.usefixtures("init_integration")
async def test_options_flow_without_polling_when_no_interval_fits(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test polling is not offered if even the longest interval is too often."""
    mock_config_entry.runtime_data.rate_limit = 100

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert [str(key) for key in result["data_schema"].schema] == [CONF_MANUAL_RUN_MINS]


@pytest.mark.parametrize(
    ("base_stations", "interval", "controller_calls", "total_calls"),
    [
        pytest.param(1, "1", "1,440", "2,208", id="hose-timers"),
        pytest.param(0, "0.5", "2,880", "2,880", id="no-hose-timers"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_options_flow_usage_placeholders(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    base_stations: int,
    interval: str,
    controller_calls: str,
    total_calls: str,
) -> None:
    """Test the estimated usage includes the smart hose timers on the account."""
    del mock_config_entry.runtime_data.base_stations[base_stations:]

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["description_placeholders"] == {
        "interval": interval,
        "controller_calls": controller_calls,
        "total_calls": total_calls,
        "daily_limit": "3,500",
    }
