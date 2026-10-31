"""Test the Xbox event platform."""

import asyncio
from collections.abc import Generator
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from httpx2 import ConnectError, HTTPStatusError, Request, Response
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
    async_load_json_object_fixture,
    load_json_object_fixture,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)
from pythonxbox.api.provider.achievements.models import (
    Achievement360Response,
    AchievementResponse,
)
from pythonxbox.api.provider.people.models import PeopleResponse
from pythonxbox.api.provider.titlehub.models import TitleHubResponse
from pythonxbox.common.exceptions import RateLimitExceededException
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.xbox.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_STATE_CHANGED, STATE_UNAVAILABLE, Platform
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State
from homeassistant.helpers import entity_registry as er

ENTITY_ID = "event.gsr_ae_achievement_unlocked"
OWN_XUID = "271958441785640"
ONLINE_FRIEND_XUID = "2533274913657542"
OFFLINE_FRIEND_XUID = "2533274838782903"
UPDATE_INTERVAL = timedelta(seconds=30)

titlehub_request = Request("GET", "https://titlehub.xboxlive.com")


@pytest.fixture(autouse=True)
def event_only() -> Generator[None]:
    """Enable only the event platform."""
    with patch(
        "homeassistant.components.xbox.PLATFORMS",
        [Platform.EVENT],
    ):
        yield


def xboxone(*names: str) -> AchievementResponse:
    """Recent Xbox One unlocks, limited to the given achievements."""
    payload = load_json_object_fixture(
        "achievements_xboxone_recent_unlocks.json", DOMAIN
    )
    payload["achievements"] = [a for a in payload["achievements"] if a["name"] in names]
    return AchievementResponse(**payload)


def xbox360(*names: str) -> Achievement360Response:
    """Recent Xbox 360 unlocks, limited to the given achievements."""
    payload = load_json_object_fixture(
        "achievements_xbox360_recent_unlocks.json", DOMAIN
    )
    payload["achievements"] = [a for a in payload["achievements"] if a["name"] in names]
    return Achievement360Response(**payload)


def unlocked(events: list[Event[EventStateChangedData]]) -> list[str]:
    """Names of the achievements announced, in order."""
    return [
        event.data["new_state"].attributes["name"]
        for event in events
        if event.data["entity_id"] == ENTITY_ID
        and event.data["old_state"] is not None
        and event.data["new_state"] is not None
    ]


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the Xbox integration."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def next_update(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Advance to the next presence update."""
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.freeze_time("2026-09-13T15:00:00+00:00")
@pytest.mark.usefixtures("xbox_live_client")
async def test_event_platform(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the Xbox event platform."""

    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.freeze_time("2026-09-13T15:00:00+00:00")
async def test_xboxone_unlocks(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    xbox_live_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test new Xbox One unlocks are announced, oldest first."""
    achievements = xbox_live_client.achievements
    achievements.get_achievements_xboxone_recent_unlocks.return_value = xboxone(
        "Complete Collection", "Racking Up The Miles"
    )
    events = async_capture_events(hass, EVENT_STATE_CHANGED)

    await setup_integration(hass, config_entry)

    assert unlocked(events) == []
    state = hass.states.get(ENTITY_ID)
    assert state
    assert "entity_picture" not in state.attributes

    achievements.get_achievements_xboxone_recent_unlocks.return_value = xboxone(
        "Pork Chop", "Cow Tipper", "Complete Collection", "Racking Up The Miles"
    )
    await next_update(hass, freezer)

    assert unlocked(events) == ["Cow Tipper", "Pork Chop"]
    state = hass.states.get(ENTITY_ID)
    assert state
    # The picture follows the last unlock.
    assert state.attributes["entity_picture"] == state.attributes["image"]
    assert state == snapshot


@pytest.mark.parametrize(
    ("titlehub", "game", "titlehub_calls"),
    [
        pytest.param(
            {
                "return_value": TitleHubResponse(
                    **load_json_object_fixture(
                        "titlehub_titleinfo_xbox360.json", DOMAIN
                    )
                )
            },
            "Joy Ride Turbo",
            1,
            id="found",
        ),
        pytest.param(
            {
                "side_effect": HTTPStatusError(
                    "Not Found",
                    request=titlehub_request,
                    response=Response(404, request=titlehub_request),
                )
            },
            None,
            1,
            id="not_found",
        ),
        pytest.param(
            {
                "side_effect": HTTPStatusError(
                    "Too Many Requests",
                    request=titlehub_request,
                    response=Response(429, request=titlehub_request),
                )
            },
            None,
            4,
            id="too_many_requests",
        ),
        pytest.param(
            {"side_effect": ConnectError("Network is unreachable")},
            None,
            4,
            id="connection_error",
        ),
    ],
)
@pytest.mark.freeze_time("2021-03-06T18:50:00+00:00")
async def test_xbox360_unlocks(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    xbox_live_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    titlehub: dict[str, Any],
    game: str | None,
    titlehub_calls: int,
) -> None:
    """Test Xbox 360 unlocks are announced with the game looked up once."""
    achievements = xbox_live_client.achievements
    achievements.get_achievements_xboxone_recent_unlocks.return_value = xboxone()
    achievements.get_achievements_xbox360_recent_unlocks.return_value = xbox360(
        "Supercharged", "Databass"
    )
    xbox_live_client.titlehub.get_title_info.configure_mock(**titlehub)

    await setup_integration(hass, config_entry)

    achievements.get_achievements_xbox360_recent_unlocks.return_value = xbox360(
        "Keep on Truckin'", "Supercharged", "Databass"
    )
    await next_update(hass, freezer)

    achievements.get_achievements_xbox360_recent_unlocks.return_value = xbox360(
        "Flex Those Muscles", "Keep on Truckin'", "Supercharged", "Databass"
    )
    await next_update(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes["name"] == "Flex Those Muscles"
    assert state.attributes["game"] == game
    assert state == snapshot
    # Both people online share the mocked unlocks, and only answers are cached.
    assert xbox_live_client.titlehub.get_title_info.await_count == titlehub_calls


@pytest.mark.freeze_time("2021-03-06T18:50:00+00:00")
async def test_unlocks_announced_in_order(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    xbox_live_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a slow game lookup holds back the unlocks of the next update."""
    achievements = xbox_live_client.achievements
    achievements.get_achievements_xboxone_recent_unlocks.return_value = xboxone()
    achievements.get_achievements_xbox360_recent_unlocks.return_value = xbox360(
        "Supercharged", "Databass"
    )
    title = TitleHubResponse(
        **await async_load_json_object_fixture(
            hass, "titlehub_titleinfo_xbox360.json", DOMAIN
        )
    )
    hold = True
    release = asyncio.Event()

    async def get_title_info(title_id: str) -> TitleHubResponse:
        if hold:
            await release.wait()
        return title

    xbox_live_client.titlehub.get_title_info.side_effect = get_title_info
    events = async_capture_events(hass, EVENT_STATE_CHANGED)

    await setup_integration(hass, config_entry)

    achievements.get_achievements_xbox360_recent_unlocks.return_value = xbox360(
        "Keep on Truckin'", "Supercharged", "Databass"
    )
    await next_update(hass, freezer)

    hold = False
    achievements.get_achievements_xbox360_recent_unlocks.return_value = xbox360(
        "Flex Those Muscles", "Keep on Truckin'", "Supercharged", "Databass"
    )
    await next_update(hass, freezer)

    release.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert unlocked(events) == ["Keep on Truckin'", "Flex Those Muscles"]
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes["name"] == "Flex Those Muscles"


@pytest.mark.freeze_time("2026-09-13T16:00:00+00:00")
async def test_stale_unlocks_not_announced(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    xbox_live_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test unlocks older than an hour are not announced."""
    achievements = xbox_live_client.achievements
    achievements.get_achievements_xboxone_recent_unlocks.return_value = xboxone(
        "Complete Collection"
    )
    events = async_capture_events(hass, EVENT_STATE_CHANGED)

    await setup_integration(hass, config_entry)

    achievements.get_achievements_xboxone_recent_unlocks.return_value = xboxone(
        "Pork Chop", "Cow Tipper", "Complete Collection"
    )
    await next_update(hass, freezer)

    assert unlocked(events) == []


@pytest.mark.freeze_time("2026-09-13T15:00:00+00:00")
@pytest.mark.usefixtures("xbox_live_client")
async def test_restored_last_unlock(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test only unlocks after the restored one are announced."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(ENTITY_ID, "2026-09-13T14:20:00.000+00:00"),
                {
                    "last_event_type": "achievement_unlocked",
                    "last_event_attributes": {
                        "name": "Cow Tipper",
                        "time_unlocked": "2026-09-13T14:19:08.717000+00:00",
                    },
                },
            )
        ],
    )
    events = async_capture_events(hass, EVENT_STATE_CHANGED)

    await setup_integration(hass, config_entry)

    assert unlocked(events) == ["Pork Chop"]


@pytest.mark.freeze_time("2026-09-13T15:00:00+00:00")
async def test_reload_keeps_last_unlock(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    xbox_live_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the last unlock survives a reload, and nothing is announced again."""
    achievements = xbox_live_client.achievements
    achievements.get_achievements_xboxone_recent_unlocks.return_value = xboxone(
        "Complete Collection"
    )
    events = async_capture_events(hass, EVENT_STATE_CHANGED)

    await setup_integration(hass, config_entry)

    achievements.get_achievements_xboxone_recent_unlocks.return_value = xboxone(
        "Pork Chop", "Cow Tipper", "Complete Collection"
    )
    await next_update(hass, freezer)

    assert unlocked(events) == ["Cow Tipper", "Pork Chop"]
    state = hass.states.get(ENTITY_ID)
    assert state

    freezer.tick(timedelta(seconds=1))
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    # Restored as it was, rather than announced again.
    restored = hass.states.get(ENTITY_ID)
    assert restored
    assert restored.state == state.state
    assert restored.attributes == state.attributes


@pytest.mark.freeze_time("2026-09-13T15:00:00+00:00")
async def test_first_unlock_without_history(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    xbox_live_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the first unlock of someone without any unlocks yet is announced."""
    achievements = xbox_live_client.achievements
    achievements.get_achievements_xboxone_recent_unlocks.return_value = xboxone()
    achievements.get_achievements_xbox360_recent_unlocks.return_value = xbox360()
    events = async_capture_events(hass, EVENT_STATE_CHANGED)

    await setup_integration(hass, config_entry)

    achievements.get_achievements_xboxone_recent_unlocks.return_value = xboxone(
        "Pork Chop"
    )
    await next_update(hass, freezer)

    assert unlocked(events) == ["Pork Chop"]


async def test_polled_while_online(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    xbox_live_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test only people who are online are polled between sweeps."""
    recent_unlocks = (
        xbox_live_client.achievements.get_achievements_xboxone_recent_unlocks
    )

    await setup_integration(hass, config_entry)

    assert {call.args[0] for call in recent_unlocks.call_args_list} == {
        OWN_XUID,
        ONLINE_FRIEND_XUID,
        OFFLINE_FRIEND_XUID,
    }

    recent_unlocks.reset_mock()
    await next_update(hass, freezer)

    assert {call.args[0] for call in recent_unlocks.call_args_list} == {
        OWN_XUID,
        ONLINE_FRIEND_XUID,
    }

    recent_unlocks.reset_mock()
    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert {call.args[0] for call in recent_unlocks.call_args_list} == {
        OWN_XUID,
        ONLINE_FRIEND_XUID,
        OFFLINE_FRIEND_XUID,
    }


async def test_polled_once_after_going_offline(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    xbox_live_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test someone going offline is polled one last time."""
    recent_unlocks = (
        xbox_live_client.achievements.get_achievements_xboxone_recent_unlocks
    )

    await setup_integration(hass, config_entry)

    friends = await async_load_json_object_fixture(
        hass, "people_friends_own.json", DOMAIN
    )
    for friend in friends["people"]:
        friend["presenceState"] = "Offline"
    xbox_live_client.people.get_friends_own.return_value = PeopleResponse(**friends)

    recent_unlocks.reset_mock()
    await next_update(hass, freezer)

    assert {call.args[0] for call in recent_unlocks.call_args_list} == {
        OWN_XUID,
        ONLINE_FRIEND_XUID,
    }

    recent_unlocks.reset_mock()
    await next_update(hass, freezer)

    assert {call.args[0] for call in recent_unlocks.call_args_list} == {OWN_XUID}


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(ConnectError("Network is unreachable"), id="connection_error"),
        pytest.param(
            HTTPStatusError(
                "Server Error",
                request=Request("GET", "https://achievements.xboxlive.com"),
                response=Response(
                    500, request=Request("GET", "https://achievements.xboxlive.com")
                ),
            ),
            id="http_status_error",
        ),
        pytest.param(
            RateLimitExceededException("Rate limit exceeded", MagicMock()),
            id="rate_limit_exceeded",
        ),
    ],
)
async def test_achievements_unavailable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    xbox_live_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test one failing person is skipped, and everyone failing is unavailable."""
    recent_unlocks = (
        xbox_live_client.achievements.get_achievements_xboxone_recent_unlocks
    )
    response = recent_unlocks.return_value

    def fail_for_friend(xuid: str) -> AchievementResponse:
        if xuid == ONLINE_FRIEND_XUID:
            raise exception
        return response

    recent_unlocks.side_effect = fail_for_friend

    await setup_integration(hass, config_entry)

    state = hass.states.get("event.erics273_achievement_unlocked")
    assert state
    assert state.state != STATE_UNAVAILABLE

    recent_unlocks.side_effect = exception
    await next_update(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNAVAILABLE
