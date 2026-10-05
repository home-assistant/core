"""Test building UniFi firewall policy schedules."""

import asyncio
from collections.abc import Callable
from copy import deepcopy
from datetime import date, time
from typing import Any

from aiounifi.models.firewall_policy import FirewallPolicyScheduleMode
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)
from yarl import URL

from homeassistant.components.unifi.const import CONF_SITE_ID
from homeassistant.components.unifi.coordinator import POLL_INTERVAL
from homeassistant.components.unifi.firewall_policy_schedule import (
    build_schedule,
    parse_date,
    parse_time,
    schedule_uses_times,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant

from .conftest import ConfigEntryFactoryType
from .test_sensor import FIREWALL_POLICY

TODAY = date(2026, 1, 16)

EVERY_DAY = {
    "mode": "EVERY_DAY",
    "time_range_start": "21:00",
    "time_range_end": "08:00",
}
ONE_TIME = {
    "mode": "ONE_TIME_ONLY",
    "date": "2026-01-10",
    "time_range_start": "21:30",
    "time_range_end": "08:30",
}
WEEKLY = {
    "mode": "EVERY_WEEK",
    "repeat_on_days": ["wed", "mon"],
    "time_all_day": False,
    "time_range_start": "15:00",
    "time_range_end": "17:00",
}
WEEKLY_ALL_DAY = {"mode": "EVERY_WEEK", "repeat_on_days": ["fri"], "time_all_day": True}
CUSTOM = {
    "mode": "CUSTOM",
    "date_start": "2026-01-05",
    "date_end": "2026-01-30",
    "repeat_on_days": ["fri", "mon"],
    "time_all_day": False,
    "time_range_start": "20:00",
    "time_range_end": "06:00",
}


@pytest.mark.parametrize(
    ("current", "changes", "expected"),
    [
        # Mode changes build a clean schedule and keep the current times.
        (EVERY_DAY, {"mode": FirewallPolicyScheduleMode.ALWAYS}, {"mode": "ALWAYS"}),
        (
            EVERY_DAY,
            {"mode": FirewallPolicyScheduleMode.ONE_TIME_ONLY},
            {
                "mode": "ONE_TIME_ONLY",
                "date": "2026-01-16",
                "time_range_start": "21:00",
                "time_range_end": "08:00",
            },
        ),
        # One time keys don't leak into Every day.
        (
            ONE_TIME,
            {"mode": FirewallPolicyScheduleMode.EVERY_DAY},
            {
                "mode": "EVERY_DAY",
                "time_range_start": "21:30",
                "time_range_end": "08:30",
            },
        ),
        # Without times, the UniFi UI's defaults are used.
        (
            {"mode": "ALWAYS"},
            {"mode": FirewallPolicyScheduleMode.EVERY_DAY},
            {
                "mode": "EVERY_DAY",
                "time_range_start": "09:00",
                "time_range_end": "12:00",
            },
        ),
        # Switching to One time always dates it today, even from One time's
        # own stale date when the mode is re-selected from another mode.
        (
            WEEKLY_ALL_DAY,
            {"mode": FirewallPolicyScheduleMode.ONE_TIME_ONLY},
            {
                "mode": "ONE_TIME_ONLY",
                "date": "2026-01-16",
                "time_range_start": "09:00",
                "time_range_end": "12:00",
            },
        ),
        # Every week and Custom start with every day and today's dates.
        (
            EVERY_DAY,
            {"mode": FirewallPolicyScheduleMode.CUSTOM},
            {
                "mode": "CUSTOM",
                "date_start": "2026-01-16",
                "date_end": "2026-01-17",
                "repeat_on_days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                "time_all_day": False,
                "time_range_start": "21:00",
                "time_range_end": "08:00",
            },
        ),
        # Value changes keep the mode and everything else it uses.
        (
            EVERY_DAY,
            {"start": time(22, 15, 45)},
            {
                "mode": "EVERY_DAY",
                "time_range_start": "22:15",
                "time_range_end": "08:00",
            },
        ),
        (
            ONE_TIME,
            {"start_date": date(2026, 2, 1)},
            {
                "mode": "ONE_TIME_ONLY",
                "date": "2026-02-01",
                "time_range_start": "21:30",
                "time_range_end": "08:30",
            },
        ),
        (
            ONE_TIME,
            {"end": time(7, 0)},
            {
                "mode": "ONE_TIME_ONLY",
                "date": "2026-01-10",
                "time_range_start": "21:30",
                "time_range_end": "07:00",
            },
        ),
        # Days are sent Monday first, whatever order the controller used.
        (
            WEEKLY,
            {"end": time(18, 0)},
            {
                "mode": "EVERY_WEEK",
                "repeat_on_days": ["mon", "wed"],
                "time_all_day": False,
                "time_range_start": "15:00",
                "time_range_end": "18:00",
            },
        ),
        (
            CUSTOM,
            {"end_date": date(2026, 2, 28)},
            {
                "mode": "CUSTOM",
                "date_start": "2026-01-05",
                "date_end": "2026-02-28",
                "repeat_on_days": ["mon", "fri"],
                "time_all_day": False,
                "time_range_start": "20:00",
                "time_range_end": "06:00",
            },
        ),
        # Choosing One time again dates it today.
        (
            ONE_TIME,
            {"mode": FirewallPolicyScheduleMode.ONE_TIME_ONLY},
            {
                "mode": "ONE_TIME_ONLY",
                "date": "2026-01-16",
                "time_range_start": "21:30",
                "time_range_end": "08:30",
            },
        ),
        # A value change keeps the days as they are, even when none are chosen.
        (
            {**WEEKLY, "repeat_on_days": []},
            {"end": time(18, 0)},
            {
                "mode": "EVERY_WEEK",
                "repeat_on_days": [],
                "time_all_day": False,
                "time_range_start": "15:00",
                "time_range_end": "18:00",
            },
        ),
        # Changing between the modes with days starts over: every day, timed.
        (
            WEEKLY_ALL_DAY,
            {"mode": FirewallPolicyScheduleMode.CUSTOM},
            {
                "mode": "CUSTOM",
                "date_start": "2026-01-16",
                "date_end": "2026-01-17",
                "repeat_on_days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                "time_all_day": False,
                "time_range_start": "09:00",
                "time_range_end": "12:00",
            },
        ),
        # An all-day schedule has no times, and a stray date isn't carried.
        (
            {**WEEKLY_ALL_DAY, "date": "2026-01-01"},
            {},
            {"mode": "EVERY_WEEK", "repeat_on_days": ["fri"], "time_all_day": True},
        ),
    ],
)
def test_build_schedule(
    current: dict[str, Any], changes: dict[str, Any], expected: dict[str, Any]
) -> None:
    """A built schedule has exactly the keys its mode uses."""
    assert build_schedule(current, TODAY, **changes) == expected


@pytest.mark.parametrize(
    ("schedule", "expected"),
    [
        ({"mode": "ALWAYS"}, False),
        ({"mode": "SUNRISE"}, False),
        ({}, False),
        (EVERY_DAY, True),
        (ONE_TIME, True),
        (WEEKLY, True),
        (WEEKLY_ALL_DAY, False),
        # All day only counts in the modes that have it.
        ({**EVERY_DAY, "time_all_day": True}, True),
    ],
)
def test_schedule_uses_times(schedule: dict[str, Any], expected: bool) -> None:
    """Times apply unless the mode has none or the schedule is all day."""
    assert schedule_uses_times(schedule) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("21:30", time(21, 30)),
        ("00:00", time(0, 0)),
        ("25:00", None),
        ("9", None),
        (None, None),
        (2130, None),
    ],
)
def test_parse_time(value: object, expected: time | None) -> None:
    """Malformed times give None."""
    assert parse_time(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-01-16", date(2026, 1, 16)),
        ("2026-13-01", None),
        (None, None),
        (20260116, None),
    ],
)
def test_parse_date(value: object, expected: date | None) -> None:
    """Malformed dates give None."""
    assert parse_date(value) == expected


SELECT = "select.unifi_network_block_streaming_schedule"
START_TIME = "time.unifi_network_block_streaming_schedule_start"
END_TIME = "time.unifi_network_block_streaming_schedule_end"
START_DATE = "date.unifi_network_block_streaming_schedule_start_date"
SWITCH = "switch.unifi_network_block_streaming"


class FakeController:
    """A controller that stores the policy it is sent and returns it."""

    def __init__(
        self,
        aioclient_mock: AiohttpClientMocker,
        mock_requests: Callable[[], None],
        config_entry: MockConfigEntry,
        policy: dict[str, Any],
        *,
        json_response: bool = True,
        put_delay: float = 0.0,
    ) -> None:
        """Replace the firewall policy endpoints with stateful ones."""
        self.policy = deepcopy(policy)
        self.puts: list[dict[str, Any]] = []
        self._json_response = json_response
        self._put_delay = put_delay
        url = (
            f"https://{config_entry.data[CONF_HOST]}:1234"
            f"/v2/api/site/{config_entry.data[CONF_SITE_ID]}/firewall-policies"
        )
        # The first matching mock wins, so register these before the defaults.
        aioclient_mock.clear_requests()
        aioclient_mock.get(url, side_effect=self._get)
        aioclient_mock.put(f"{url}/{policy['_id']}", side_effect=self._put)
        mock_requests()

    async def _get(self, method: str, url: URL, data: Any) -> AiohttpClientMockResponse:
        return AiohttpClientMockResponse(
            method,
            url,
            json=[deepcopy(self.policy)],
            headers={"content-type": CONTENT_TYPE_JSON},
        )

    async def _put(self, method: str, url: URL, data: Any) -> AiohttpClientMockResponse:
        body = deepcopy(data)
        if self._put_delay:
            await asyncio.sleep(self._put_delay)
        self.puts.append(body)
        self.policy = body
        if not self._json_response:
            return AiohttpClientMockResponse(method, url)
        return AiohttpClientMockResponse(
            method,
            url,
            json=deepcopy(body),
            headers={"content-type": CONTENT_TYPE_JSON},
        )


async def _call(
    hass: HomeAssistant, domain: str, service: str, entity_id: str, **data: Any
) -> None:
    await hass.services.async_call(
        domain, service, {ATTR_ENTITY_ID: entity_id, **data}, blocking=True
    )


@pytest.mark.parametrize("json_response", [True, False])
@pytest.mark.parametrize(
    "firewall_policy_payload", [[{**FIREWALL_POLICY, "enabled": False}]]
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_schedule_set_step_by_step(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
    config_entry_factory: ConfigEntryFactoryType,
    mock_requests: Callable[[], None],
    firewall_policy_payload: list[dict[str, Any]],
    json_response: bool,
) -> None:
    """Each write builds on the one before it, and entities follow.

    The controller may or may not echo the policy back; either way the
    refresh after each write picks the change up.
    """
    freezer.move_to("2026-01-15 23:30:00+00:00")
    config_entry = await config_entry_factory()
    controller = FakeController(
        aioclient_mock,
        mock_requests,
        config_entry,
        firewall_policy_payload[0],
        json_response=json_response,
    )

    await _call(hass, "select", "select_option", SELECT, option="one_time")
    assert hass.states.get(SELECT).state == "one_time"
    assert hass.states.get(START_DATE).state == "2026-01-16"

    await _call(hass, "date", "set_value", START_DATE, date="2026-01-17")
    await _call(hass, "time", "set_value", START_TIME, time="22:15:30")
    await _call(hass, "time", "set_value", END_TIME, time="07:00:00")
    await _call(hass, "switch", "turn_on", SWITCH)

    assert len(controller.puts) == 5
    assert controller.policy["enabled"] is True
    assert controller.policy["schedule"] == {
        "mode": "ONE_TIME_ONLY",
        "date": "2026-01-17",
        "time_range_start": "22:15",
        "time_range_end": "07:00",
    }
    assert hass.states.get(SELECT).state == "one_time"
    assert hass.states.get(START_DATE).state == "2026-01-17"
    assert hass.states.get(START_TIME).state == "22:15:00"
    assert hass.states.get(END_TIME).state == "07:00:00"
    assert hass.states.get(SWITCH).state == "on"


@pytest.mark.parametrize("firewall_policy_payload", [[FIREWALL_POLICY]])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_schedule_entities_follow_polling(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
    config_entry_factory: ConfigEntryFactoryType,
    mock_requests: Callable[[], None],
) -> None:
    """A schedule changed on the controller shows up after the next poll."""
    config_entry = await config_entry_factory()
    controller = FakeController(
        aioclient_mock, mock_requests, config_entry, FIREWALL_POLICY
    )
    assert hass.states.get(SELECT).state == "every_day"

    controller.policy["schedule"] = {
        "mode": "ONE_TIME_ONLY",
        "date": "2026-02-01",
        "time_range_start": "19:00",
        "time_range_end": "06:30",
    }
    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(SELECT).state == "one_time"
    assert hass.states.get(START_DATE).state == "2026-02-01"
    assert hass.states.get(START_TIME).state == "19:00:00"
    assert hass.states.get(END_TIME).state == "06:30:00"


@pytest.mark.parametrize("firewall_policy_payload", [[FIREWALL_POLICY]])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_simultaneous_writes_are_not_lost(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_factory: ConfigEntryFactoryType,
    mock_requests: Callable[[], None],
) -> None:
    """Writes from different platforms at the same time both take effect.

    Each write sends the whole policy, so they must not build on the same
    cached copy.
    """
    config_entry = await config_entry_factory()
    controller = FakeController(
        aioclient_mock, mock_requests, config_entry, FIREWALL_POLICY, put_delay=0.05
    )

    await asyncio.gather(
        _call(hass, "time", "set_value", START_TIME, time="22:15:00"),
        _call(hass, "switch", "turn_off", SWITCH),
    )

    assert controller.policy["enabled"] is False
    assert controller.policy["schedule"]["time_range_start"] == "22:15"
    assert hass.states.get(START_TIME).state == "22:15:00"
    assert hass.states.get(SWITCH).state == "off"
