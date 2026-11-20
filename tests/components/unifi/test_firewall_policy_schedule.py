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

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SelectService,
    SelectServiceArgument,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchService
from homeassistant.components.unifi.const import CONF_SITE_ID, DOMAIN
from homeassistant.components.unifi.coordinator import POLL_INTERVAL
from homeassistant.const import CONF_HOST, CONTENT_TYPE_JSON, CommonServiceArgument
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import ConfigEntryFactoryType
from .test_sensor import FIREWALL_POLICY

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
        self.held_gets: asyncio.Queue[asyncio.Event] = asyncio.Queue()
        """Each GET held open, in order; set its event to answer it."""
        self.hold_gets = False
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
        # Answer with the policy as it was when the request was sent.
        policy = deepcopy(self.policy)
        if self.hold_gets:
            release = asyncio.Event()
            self.held_gets.put_nowait(release)
            await release.wait()
        return AiohttpClientMockResponse(
            method,
            url,
            json=[policy],
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
    await _call(hass, SWITCH_DOMAIN, SwitchService.TURN_ON, SWITCH)

    # One time is dated today by the controller's clock, already the 16th.
    assert len(controller.puts) == 2
    assert controller.policy["enabled"] is True
    assert controller.policy["schedule"] == {
        "mode": "ONE_TIME_ONLY",
        "date": "2026-01-16",
        "time_range_start": "21:00",
        "time_range_end": "08:00",
    }
    assert hass.states.get(SELECT).state == "one_time"
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


@pytest.mark.parametrize("json_response", [True, False])
@pytest.mark.parametrize("firewall_policy_payload", [[FIREWALL_POLICY]])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_simultaneous_writes_are_not_lost(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_factory: ConfigEntryFactoryType,
    mock_requests: Callable[[], None],
    json_response: bool,
) -> None:
    """Writes from different platforms at the same time both take effect.

    Each write sends the whole policy, so they must not build on the same
    cached copy, whether or not the controller sends the saved policy back.
    """
    config_entry = await config_entry_factory()
    controller = FakeController(
        aioclient_mock,
        mock_requests,
        config_entry,
        FIREWALL_POLICY,
        json_response=json_response,
        put_delay=0.05,
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


async def _run_ready_tasks() -> None:
    """Let tasks run until they block (frozen time stops asyncio.sleep)."""
    for _ in range(50):
        await asyncio.sleep(0)


@pytest.mark.parametrize("firewall_policy_payload", [[FIREWALL_POLICY]])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_poll_sent_before_a_write_does_not_undo_it(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    config_entry_factory: ConfigEntryFactoryType,
    aioclient_mock: AiohttpClientMocker,
    mock_requests: Callable[[], None],
) -> None:
    """A poll answered after a write can't put back the policy it replaced.

    Otherwise the next write, built from the cached policy, would send the
    old schedule back to the controller.
    """
    config_entry = await config_entry_factory()
    controller = FakeController(
        aioclient_mock, mock_requests, config_entry, FIREWALL_POLICY
    )
    controller.hold_gets = True

    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    poll = await controller.held_gets.get()

    select = hass.async_create_task(
        _call(
            hass,
            SELECT_DOMAIN,
            SelectService.SELECT_OPTION,
            SELECT,
            {SelectServiceArgument.OPTION: "always"},
        )
    )
    await _run_ready_tasks()
    poll.set()
    # The refresh after the schedule write waits behind the poll.
    refresh = await controller.held_gets.get()

    switch = hass.async_create_task(
        _call(hass, SWITCH_DOMAIN, SwitchService.TURN_OFF, SWITCH)
    )
    await _run_ready_tasks()
    controller.hold_gets = False
    refresh.set()
    await asyncio.gather(select, switch)

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
        (SWITCH_DOMAIN, SwitchService.TURN_OFF, SWITCH, {}),
    ],
)
@pytest.mark.parametrize(
    "firewall_policy_payload", [[{**FIREWALL_POLICY, "schedule": CUSTOM}]]
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_rejected_write_raises_a_translated_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    domain: str,
    service: str,
    entity_id: str,
    data: dict[str, Any],
) -> None:
    """A write UniFi Network rejects raises a translated error."""
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
    assert exc_info.value.translation_key == "action_request_failed"


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
