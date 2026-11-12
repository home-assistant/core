"""Test changing UniFi firewall policy schedules through their entities."""

import asyncio
from collections.abc import Callable
from copy import deepcopy
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)
from yarl import URL

from homeassistant.components.date import (
    DOMAIN as DATE_DOMAIN,
    DateService,
    DateServiceArgument,
)
from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SelectService,
    SelectServiceArgument,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchService
from homeassistant.components.time import (
    DOMAIN as TIME_DOMAIN,
    TimeService,
    TimeServiceArgument,
)
from homeassistant.components.unifi.const import CONF_SITE_ID, DOMAIN
from homeassistant.components.unifi.coordinator import POLL_INTERVAL
from homeassistant.const import CONF_HOST, CONTENT_TYPE_JSON, CommonServiceArgument
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import ConfigEntryFactoryType
from .test_sensor import FIREWALL_POLICY

WEEKLY = {
    "mode": "EVERY_WEEK",
    "repeat_on_days": ["wed", "mon"],
    "time_all_day": False,
    "time_range_start": "15:00",
    "time_range_end": "17:00",
}
CUSTOM = {
    "mode": "CUSTOM",
    "date_start": "2026-01-05",
    "date_end": "2026-01-30",
    "repeat_on_days": ["fri", "mon"],
    "time_all_day": False,
    "time_range_start": "20:00",
    "time_range_end": "06:00",
}
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
    hass: HomeAssistant,
    domain: str,
    service: str,
    entity_id: str,
    data: dict[str, Any] | None = None,
) -> None:
    await hass.services.async_call(
        domain,
        service,
        {CommonServiceArgument.ENTITY_ID: entity_id, **(data or {})},
        blocking=True,
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

    await _call(
        hass,
        SELECT_DOMAIN,
        SelectService.SELECT_OPTION,
        SELECT,
        {SelectServiceArgument.OPTION: "one_time"},
    )
    assert hass.states.get(SELECT).state == "one_time"
    # One time is dated today by the controller's clock, already the 16th.
    assert hass.states.get(START_DATE).state == "2026-01-16"

    await _call(
        hass,
        DATE_DOMAIN,
        DateService.SET_VALUE,
        START_DATE,
        {DateServiceArgument.DATE: "2026-01-17"},
    )
    await _call(
        hass,
        TIME_DOMAIN,
        TimeService.SET_VALUE,
        START_TIME,
        {TimeServiceArgument.TIME: "22:15:30"},
    )
    await _call(
        hass,
        TIME_DOMAIN,
        TimeService.SET_VALUE,
        END_TIME,
        {TimeServiceArgument.TIME: "07:00:00"},
    )
    await _call(hass, SWITCH_DOMAIN, SwitchService.TURN_ON, SWITCH)

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
        _call(
            hass,
            SELECT_DOMAIN,
            SelectService.SELECT_OPTION,
            SELECT,
            {SelectServiceArgument.OPTION: "always"},
        ),
        _call(hass, SWITCH_DOMAIN, SwitchService.TURN_OFF, SWITCH),
    )

    assert controller.policy["enabled"] is False
    assert controller.policy["schedule"] == {"mode": "ALWAYS"}
    assert hass.states.get(SELECT).state == "always"
    assert hass.states.get(SWITCH).state == "off"


REJECTION = {
    "code": "api.err.InvalidDateRange",
    "details": {},
    "errorCode": 400,
    "message": "Start date must be before the end date",
}


@pytest.mark.parametrize(
    ("domain", "service", "entity_id", "data"),
    [
        (
            SELECT_DOMAIN,
            SelectService.SELECT_OPTION,
            SELECT,
            {SelectServiceArgument.OPTION: "always"},
        ),
        (
            TIME_DOMAIN,
            TimeService.SET_VALUE,
            START_TIME,
            {TimeServiceArgument.TIME: "20:30:00"},
        ),
        (
            DATE_DOMAIN,
            DateService.SET_VALUE,
            "date.unifi_network_block_streaming_schedule_end_date",
            {DateServiceArgument.DATE: "2026-02-28"},
        ),
        (SWITCH_DOMAIN, SwitchService.TURN_OFF, SWITCH, {}),
    ],
)
@pytest.mark.parametrize(
    "firewall_policy_payload", [[{**FIREWALL_POLICY, "schedule": CUSTOM}]]
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_rejected_write_shows_the_controllers_reason(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    domain: str,
    service: str,
    entity_id: str,
    data: dict[str, Any],
) -> None:
    """When UniFi Network rejects a write, its reason reaches the user."""
    aioclient_mock.put(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/v2/api/site/{config_entry_setup.data[CONF_SITE_ID]}"
        f"/firewall-policies/{FIREWALL_POLICY['_id']}",
        status=400,
        json=REJECTION,
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await _call(hass, domain, service, entity_id, data)

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "action_request_rejected"
    assert exc_info.value.translation_placeholders == {
        "reason": "Start date must be before the end date"
    }


@pytest.mark.parametrize("firewall_policy_payload", [[FIREWALL_POLICY]])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_rejected_switch_write_leaves_the_policy_unchanged(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
) -> None:
    """A rejected turn off leaves the cached policy and the switch on."""
    aioclient_mock.put(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/v2/api/site/{config_entry_setup.data[CONF_SITE_ID]}"
        f"/firewall-policies/{FIREWALL_POLICY['_id']}",
        status=400,
        json=REJECTION,
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    with pytest.raises(HomeAssistantError):
        await _call(hass, SWITCH_DOMAIN, SwitchService.TURN_OFF, SWITCH)

    api = config_entry_setup.runtime_data.api
    assert api.firewall_policies[FIREWALL_POLICY["_id"]].enabled is True
    assert hass.states.get(SWITCH).state == "on"


DAY_SWITCH = "switch.unifi_network_block_streaming_schedule_{}"
ALL_DAY_SWITCH = "switch.unifi_network_block_streaming_schedule_all_day"


@pytest.mark.parametrize(
    "firewall_policy_payload",
    [
        [
            {
                **FIREWALL_POLICY,
                "schedule": {
                    "mode": "EVERY_WEEK",
                    "repeat_on_days": [],
                    "time_all_day": False,
                    "time_range_start": "21:30",
                    "time_range_end": "08:30",
                },
            }
        ]
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_schedule_days_step_by_step(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_factory: ConfigEntryFactoryType,
    mock_requests: Callable[[], None],
    firewall_policy_payload: list[dict[str, Any]],
) -> None:
    """Days and all day can be set on a schedule that starts with no days."""
    config_entry = await config_entry_factory()
    controller = FakeController(
        aioclient_mock, mock_requests, config_entry, firewall_policy_payload[0]
    )
    for day in ("monday", "tuesday", "sunday"):
        assert hass.states.get(DAY_SWITCH.format(day)).state == "off"

    await _call(
        hass, SWITCH_DOMAIN, SwitchService.TURN_ON, DAY_SWITCH.format("tuesday")
    )
    assert controller.policy["schedule"]["repeat_on_days"] == ["tue"]
    assert hass.states.get(DAY_SWITCH.format("tuesday")).state == "on"
    assert hass.states.get(DAY_SWITCH.format("monday")).state == "off"

    await _call(hass, SWITCH_DOMAIN, SwitchService.TURN_ON, ALL_DAY_SWITCH)
    assert controller.policy["schedule"] == {
        "mode": "EVERY_WEEK",
        "repeat_on_days": ["tue"],
        "time_all_day": True,
    }
    assert hass.states.get(ALL_DAY_SWITCH).state == "on"
    assert hass.states.get(START_TIME).state == "unknown"

    await _call(hass, SWITCH_DOMAIN, SwitchService.TURN_OFF, ALL_DAY_SWITCH)
    assert controller.policy["schedule"] == {
        "mode": "EVERY_WEEK",
        "repeat_on_days": ["tue"],
        "time_all_day": False,
        "time_range_start": "09:00",
        "time_range_end": "12:00",
    }
    assert hass.states.get(ALL_DAY_SWITCH).state == "off"
    assert hass.states.get(START_TIME).state == "09:00:00"
    assert len(controller.puts) == 3


@pytest.mark.parametrize(
    "firewall_policy_payload", [[{**FIREWALL_POLICY, "schedule": CUSTOM}]]
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_custom_schedule_day_keeps_dates(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_factory: ConfigEntryFactoryType,
    mock_requests: Callable[[], None],
    firewall_policy_payload: list[dict[str, Any]],
) -> None:
    """Changing a day in a Custom schedule keeps its date range and times."""
    config_entry = await config_entry_factory()
    controller = FakeController(
        aioclient_mock, mock_requests, config_entry, firewall_policy_payload[0]
    )

    await _call(
        hass, SWITCH_DOMAIN, SwitchService.TURN_ON, DAY_SWITCH.format("wednesday")
    )

    assert controller.policy["schedule"] == {
        **CUSTOM,
        "repeat_on_days": ["mon", "wed", "fri"],
    }
    assert hass.states.get(DAY_SWITCH.format("wednesday")).state == "on"


@pytest.mark.parametrize(
    "firewall_policy_payload", [[{**FIREWALL_POLICY, "schedule": WEEKLY}]]
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_simultaneous_day_and_time_writes_are_not_lost(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_factory: ConfigEntryFactoryType,
    mock_requests: Callable[[], None],
    firewall_policy_payload: list[dict[str, Any]],
) -> None:
    """A day switch and a time changed at the same moment both take effect."""
    config_entry = await config_entry_factory()
    controller = FakeController(
        aioclient_mock,
        mock_requests,
        config_entry,
        firewall_policy_payload[0],
        put_delay=0.05,
    )

    await asyncio.gather(
        _call(hass, SWITCH_DOMAIN, SwitchService.TURN_ON, DAY_SWITCH.format("friday")),
        _call(
            hass,
            TIME_DOMAIN,
            TimeService.SET_VALUE,
            START_TIME,
            {TimeServiceArgument.TIME: "16:00:00"},
        ),
    )

    assert controller.policy["schedule"]["repeat_on_days"] == ["mon", "wed", "fri"]
    assert controller.policy["schedule"]["time_range_start"] == "16:00"
