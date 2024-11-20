"""Tests for Habitica button platform."""

from collections.abc import Generator
from http import HTTPStatus
import re
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.habitica.const import DEFAULT_URL, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import mock_called_with

from tests.common import MockConfigEntry, load_json_object_fixture, snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(autouse=True)
def button_only() -> Generator[None]:
    """Enable only the button platform."""
    with patch(
        "homeassistant.components.habitica.PLATFORMS",
        [Platform.BUTTON],
    ):
        yield


@pytest.mark.parametrize(
    "fixture",
    [
        "wizard_fixture",
        "rogue_fixture",
        "warrior_fixture",
        "healer_fixture",
    ],
)
async def test_buttons(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    fixture: str,
) -> None:
    """Test button entities."""
    aioclient_mock.get(
        f"{DEFAULT_URL}/api/v3/user",
        json=load_json_object_fixture(f"{fixture}.json", DOMAIN),
    )
    aioclient_mock.get(
        f"{DEFAULT_URL}/api/v3/tasks/user",
        params={"type": "completedTodos"},
        json=load_json_object_fixture("completed_todos.json", DOMAIN),
    )
    aioclient_mock.get(
        f"{DEFAULT_URL}/api/v3/tasks/user",
        json=load_json_object_fixture("tasks.json", DOMAIN),
    )
    aioclient_mock.get(
        f"{DEFAULT_URL}/api/v3/content",
        params={"language": "en"},
        json=load_json_object_fixture("content.json", DOMAIN),
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "api_url", "fixture"),
    [
        ("button.test_user_allocate_all_stat_points", "user/allocate-now", "user"),
        ("button.test_user_buy_a_health_potion", "user/buy-health-potion", "user"),
        ("button.test_user_revive_from_death", "user/revive", "user"),
        ("button.test_user_start_my_day", "cron", "user"),
        (
            "button.test_user_chilling_frost",
            "user/class/cast/frost",
            "wizard_fixture",
        ),
        (
            "button.test_user_earthquake",
            "user/class/cast/earth",
            "wizard_fixture",
        ),
        (
            "button.test_user_ethereal_surge",
            "user/class/cast/mpheal",
            "wizard_fixture",
        ),
        (
            "button.test_user_stealth",
            "user/class/cast/stealth",
            "rogue_fixture",
        ),
        (
            "button.test_user_tools_of_the_trade",
            "user/class/cast/toolsOfTrade",
            "rogue_fixture",
        ),
        (
            "button.test_user_defensive_stance",
            "user/class/cast/defensiveStance",
            "warrior_fixture",
        ),
        (
            "button.test_user_intimidating_gaze",
            "user/class/cast/intimidate",
            "warrior_fixture",
        ),
        (
            "button.test_user_valorous_presence",
            "user/class/cast/valorousPresence",
            "warrior_fixture",
        ),
        (
            "button.test_user_healing_light",
            "user/class/cast/heal",
            "healer_fixture",
        ),
        (
            "button.test_user_protective_aura",
            "user/class/cast/protectAura",
            "healer_fixture",
        ),
        (
            "button.test_user_searing_brightness",
            "user/class/cast/brightness",
            "healer_fixture",
        ),
        (
            "button.test_user_blessing",
            "user/class/cast/healAll",
            "healer_fixture",
        ),
    ],
)
async def test_button_press(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    entity_id: str,
    api_url: str,
    fixture: str,
) -> None:
    """Test button press method."""
    aioclient_mock.get(
        f"{DEFAULT_URL}/api/v3/user",
        json=load_json_object_fixture(f"{fixture}.json", DOMAIN),
    )
    aioclient_mock.get(
        f"{DEFAULT_URL}/api/v3/tasks/user",
        params={"type": "completedTodos"},
        json=load_json_object_fixture("completed_todos.json", DOMAIN),
    )
    aioclient_mock.get(
        f"{DEFAULT_URL}/api/v3/tasks/user",
        json=load_json_object_fixture("tasks.json", DOMAIN),
    )
    aioclient_mock.get(
        f"{DEFAULT_URL}/api/v3/content",
        params={"language": "en"},
        json=load_json_object_fixture("content.json", DOMAIN),
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    aioclient_mock.post(f"{DEFAULT_URL}/api/v3/{api_url}", json={"data": None})

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert mock_called_with(aioclient_mock, "post", f"{DEFAULT_URL}/api/v3/{api_url}")


@pytest.mark.parametrize(
    ("entity_id", "api_url"),
    [
        ("button.test_user_allocate_all_stat_points", "user/allocate-now"),
        ("button.test_user_buy_a_health_potion", "user/buy-health-potion"),
        ("button.test_user_revive_from_death", "user/revive"),
        ("button.test_user_start_my_day", "cron"),
        ("button.test_user_chilling_frost", "user/class/cast/frost"),
        ("button.test_user_earthquake", "user/class/cast/earth"),
        ("button.test_user_ethereal_surge", "user/class/cast/mpheal"),
    ],
    ids=[
        "allocate-points",
        "health-potion",
        "revive",
        "run-cron",
        "chilling frost",
        "earthquake",
        "ethereal surge",
    ],
)
@pytest.mark.parametrize(
    ("status_code", "msg", "exception"),
    [
        (
            HTTPStatus.TOO_MANY_REQUESTS,
            "Rate limit exceeded, try again later",
            ServiceValidationError,
        ),
        (
            HTTPStatus.BAD_REQUEST,
            "Unable to connect to Habitica, try again later",
            HomeAssistantError,
        ),
        (
            HTTPStatus.UNAUTHORIZED,
            "Unable to complete action, the required conditions are not met",
            ServiceValidationError,
        ),
    ],
)
async def test_button_press_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    entity_id: str,
    api_url: str,
    status_code: HTTPStatus,
    msg: str,
    exception: Exception,
) -> None:
    """Test button press exceptions."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_habitica.post(
        f"{DEFAULT_URL}/api/v3/{api_url}",
        status=status_code,
        json={"data": None},
    )

    with pytest.raises(exception, match=msg):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    assert mock_called_with(mock_habitica, "post", f"{DEFAULT_URL}/api/v3/{api_url}")


@pytest.mark.parametrize(
    ("fixture", "entity_ids"),
    [
        (
            "common_buttons_unavailable",
            [
                "button.test_user_allocate_all_stat_points",
                "button.test_user_revive_from_death",
                "button.test_user_buy_a_health_potion",
                "button.test_user_start_my_day",
            ],
        ),
        (
            "wizard_skills_unavailable",
            [
                "button.test_user_chilling_frost",
                "button.test_user_earthquake",
                "button.test_user_ethereal_surge",
            ],
        ),
        ("wizard_frost_unavailable", ["button.test_user_chilling_frost"]),
        (
            "rogue_skills_unavailable",
            ["button.test_user_tools_of_the_trade", "button.test_user_stealth"],
        ),
        ("rogue_stealth_unavailable", ["button.test_user_stealth"]),
        (
            "warrior_skills_unavailable",
            [
                "button.test_user_defensive_stance",
                "button.test_user_intimidating_gaze",
                "button.test_user_valorous_presence",
            ],
        ),
        (
            "healer_skills_unavailable",
            [
                "button.test_user_healing_light",
                "button.test_user_protective_aura",
                "button.test_user_searing_brightness",
                "button.test_user_blessing",
            ],
        ),
    ],
)
async def test_button_unavailable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    fixture: str,
    entity_ids: list[str],
) -> None:
    """Test buttons are unavailable if conditions are not met."""

    aioclient_mock.get(
        f"{DEFAULT_URL}/api/v3/user",
        json=load_json_object_fixture(f"{fixture}.json", DOMAIN),
    )
    aioclient_mock.get(
        f"{DEFAULT_URL}/api/v3/tasks/user",
        json=load_json_object_fixture("tasks.json", DOMAIN),
    )
    aioclient_mock.get(re.compile(r".*"), json={"data": []})

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    for entity_id in entity_ids:
        assert (state := hass.states.get(entity_id))
        assert state.state == STATE_UNAVAILABLE
