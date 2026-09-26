"""Tests for the Xbox coordinators."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from httpx import ConnectError, HTTPStatusError, Request, Response
import pytest
from pythonxbox.api.provider.achievements.models import AchievementResponse
from pythonxbox.api.provider.titlehub.models import TitleHubResponse

from homeassistant.components.xbox.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_object_fixture,
)

PRESENCE_INTERVAL = 30
TRUE_TOTAL = 43


def zeroed_title(xuid: str, _: str) -> TitleHubResponse:
    """Each person's own title, as titlehub reports an Xbox One game with unlocks."""
    payload = load_json_object_fixture(f"titlehub_titleinfo_{xuid}.json", DOMAIN)
    achievement = payload["titles"][0]["achievement"]
    achievement["totalAchievements"] = 0
    achievement["sourceVersion"] = 2
    return TitleHubResponse(**payload)


def gameprogress(total: int) -> AchievementResponse:
    """An achievements response carrying the total that matters."""
    return AchievementResponse(
        achievements=[], pagingInfo={"continuationToken": None, "totalRecords": total}
    )


@pytest.fixture(name="zero_total")
def mock_zero_total(xbox_live_client: AsyncMock) -> AsyncMock:
    """Report a zero achievement total from titlehub."""
    xbox_live_client.titlehub.get_title_info_by_xuid.side_effect = zeroed_title
    return xbox_live_client


async def test_achievement_total_retried_after_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    zero_total: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test achievement total is retried after a failed lookup."""
    achievements = zero_total.achievements
    achievements.get_achievements_xboxone_gameprogress.side_effect = ConnectError(
        "Network is unreachable"
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.gsr_ae_now_playing")
    assert state
    assert state.attributes["achievements"] == "2 / 0"

    achievements.get_achievements_xboxone_gameprogress.side_effect = None
    achievements.get_achievements_xboxone_gameprogress.return_value = gameprogress(
        TRUE_TOTAL
    )

    freezer.tick(PRESENCE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.gsr_ae_now_playing")
    assert state
    assert state.attributes["achievements"] == f"2 / {TRUE_TOTAL}"


async def test_achievement_total_fetched_once(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    zero_total: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test achievement total is only fetched once."""
    achievements = zero_total.achievements
    achievements.get_achievements_xboxone_gameprogress.return_value = gameprogress(
        TRUE_TOTAL
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    call_count = achievements.get_achievements_xboxone_gameprogress.await_count

    freezer.tick(PRESENCE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert achievements.get_achievements_xboxone_gameprogress.await_count == call_count


async def test_achievement_total_failure_keeps_entities_available(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    zero_total: AsyncMock,
) -> None:
    """Test entities stay available when the achievement lookup fails."""
    request = Request("GET", "https://achievements.xboxlive.com")
    zero_total.achievements.get_achievements_xboxone_gameprogress.side_effect = (
        HTTPStatusError(
            "Server Error", request=request, response=Response(500, request=request)
        )
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.gsr_ae_now_playing")
    assert state
    assert state.state != "unavailable"
    assert state.attributes["achievements"] == "2 / 0"
