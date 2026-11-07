"""Tests for the optional polling of Rachio controllers."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from requests.exceptions import Timeout

from homeassistant.components.rachio.const import (
    CONF_MANUAL_RUN_MINS,
    CONF_POLL_ENABLED,
    CONF_POLL_INTERVAL,
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
from homeassistant.data_entry_flow import FlowResultType, InvalidData
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

POLLING_OPTIONS = {CONF_POLLING: {CONF_POLL_ENABLED: True, CONF_POLL_INTERVAL: 1}}

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


def _running(ends_in: timedelta = timedelta(minutes=2)) -> tuple[dict, dict[str, Any]]:
    """Return a current_schedule response for a zone and schedule that is running."""
    end = dt_util.utcnow() + ends_in
    duration = 120
    start = end - timedelta(seconds=duration)
    return (
        {"status": 200},
        {
            "zoneId": ZONE_ID,
            "scheduleId": SCHEDULE_ID,
            "zoneStartDate": int(start.timestamp() * 1000),
            "zoneDuration": duration,
        },
    )


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


@pytest.fixture
def running_zone(freezer: FrozenDateTimeFactory, mock_rachio: MagicMock) -> None:
    """Report a zone that is due to finish in 90 seconds from the start."""
    mock_rachio.device.current_schedule.return_value = _running(timedelta(seconds=90))


@pytest.mark.parametrize(
    "mock_config_entry",
    [{CONF_POLLING: {CONF_POLL_ENABLED: True, CONF_POLL_INTERVAL: 5}}],
    indirect=True,
)
@pytest.mark.usefixtures("running_zone", "init_integration")
async def test_poll_after_zone_is_due_to_finish(
    hass: HomeAssistant, mock_rachio: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test the end of a run is noticed before the next regular poll."""
    assert hass.states.is_state(ZONE_ENTITY_ID, STATE_ON)
    calls = mock_rachio.device.current_schedule.call_count

    mock_rachio.device.current_schedule.return_value = ({"status": 200}, {})
    await _advance(hass, freezer, timedelta(seconds=89))
    assert mock_rachio.device.current_schedule.call_count == calls
    assert hass.states.is_state(ZONE_ENTITY_ID, STATE_ON)

    await _advance(hass, freezer, timedelta(seconds=5))
    assert mock_rachio.device.current_schedule.call_count == calls + 1
    assert hass.states.is_state(ZONE_ENTITY_ID, STATE_OFF)

    await _advance(hass, freezer, timedelta(seconds=30))
    assert mock_rachio.device.current_schedule.call_count == calls + 1


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
@pytest.mark.parametrize("error", [Timeout, ConnectionError])
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


@pytest.mark.parametrize("mock_config_entry", [POLLING_OPTIONS], indirect=True)
@pytest.mark.parametrize("status", [401, 403])
@pytest.mark.usefixtures("init_integration")
async def test_poll_auth_failure_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
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


@pytest.mark.parametrize(
    "mock_config_entry",
    [{CONF_POLLING: {CONF_POLL_ENABLED: True, CONF_POLL_INTERVAL: 0.5}}],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_saved_interval_is_raised_to_the_minimum(
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a saved interval that is now too short for the account is raised."""
    coordinator = mock_config_entry.runtime_data.controllers[0].poll_coordinator
    assert coordinator.update_interval == timedelta(minutes=1)


@pytest.mark.parametrize("mock_config_entry", [POLLING_OPTIONS], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_polling_pauses_when_few_calls_remain(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rachio: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test polling stops, says so in the log, and resumes after the limit resets."""
    coordinator = mock_config_entry.runtime_data.controllers[0].poll_coordinator
    reset = dt_util.utcnow() + timedelta(hours=2)
    headers = {
        "status": 200,
        "x-ratelimit-remaining": "10",
        "x-ratelimit-reset": reset.isoformat(),
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
    assert "Choose a longer polling interval" in caplog.text

    mock_rachio.device.current_schedule.return_value = (
        {**headers, "x-ratelimit-remaining": "3500"},
        {},
    )
    await _advance(hass, freezer, timedelta(hours=2))

    assert mock_rachio.device.current_schedule.call_count == calls + 1
    assert coordinator.last_update_success
    assert hass.states.is_state(ZONE_ENTITY_ID, STATE_OFF)


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
    assert result["description_placeholders"]["min_interval"] == "1"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_MANUAL_RUN_MINS: 5,
            CONF_POLLING: {CONF_POLL_ENABLED: True, CONF_POLL_INTERVAL: 1},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {
        CONF_MANUAL_RUN_MINS: 5,
        CONF_POLLING: {CONF_POLL_ENABLED: True, CONF_POLL_INTERVAL: 1},
    }


@pytest.mark.usefixtures("init_integration")
async def test_options_flow_interval_below_minimum(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test an interval that would exceed the API limit is rejected."""
    mock_config_entry.runtime_data.rate_limit = 1700

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["description_placeholders"]["min_interval"] == "2"

    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_MANUAL_RUN_MINS: 10,
                CONF_POLLING: {CONF_POLL_ENABLED: True, CONF_POLL_INTERVAL: 1},
            },
        )


@pytest.mark.parametrize(
    ("hose_timers", "total_calls"),
    [
        pytest.param(True, "1,056", id="hose-timers"),
        pytest.param(False, "288", id="no-hose-timers"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_options_flow_usage_placeholders(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    hose_timers: bool,
    total_calls: str,
) -> None:
    """Test the estimated usage includes the smart hose timers on the account."""
    if not hose_timers:
        mock_config_entry.runtime_data.base_stations.clear()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    placeholders = result["description_placeholders"]
    assert placeholders["interval"] == "5"
    assert placeholders["controller_calls"] == "288"
    assert placeholders["total_calls"] == total_calls
