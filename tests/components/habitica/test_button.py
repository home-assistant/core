"""Tests for Habitica button platform."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from habiticalib import HabiticaUserResponse, Skill
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.habitica.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import ERROR_BAD_REQUEST, ERROR_NOT_AUTHORIZED, ERROR_TOO_MANY_REQUESTS

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_fixture,
    snapshot_platform,
)


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
    habitica: AsyncMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    fixture: str,
) -> None:
    """Test button entities."""

    habitica.get_user.return_value = HabiticaUserResponse.from_json(
        load_fixture(f"{fixture}.json", DOMAIN)
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "call_func", "call_args", "fixture"),
    [
        (
            "button.test_user_allocate_all_stat_points",
            "allocate_stat_points",
            None,
            "user",
        ),
        ("button.test_user_buy_a_health_potion", "buy_health_potion", None, "user"),
        ("button.test_user_revive_from_death", "revive", None, "user"),
        ("button.test_user_start_my_day", "run_cron", None, "user"),
        (
            "button.test_user_chilling_frost",
            "cast_skill",
            Skill.CHILLING_FROST,
            "wizard_fixture",
        ),
        (
            "button.test_user_earthquake",
            "cast_skill",
            Skill.EARTHQUAKE,
            "wizard_fixture",
        ),
        (
            "button.test_user_ethereal_surge",
            "cast_skill",
            Skill.ETHEREAL_SURGE,
            "wizard_fixture",
        ),
        (
            "button.test_user_stealth",
            "cast_skill",
            Skill.STEALTH,
            "rogue_fixture",
        ),
        (
            "button.test_user_tools_of_the_trade",
            "cast_skill",
            Skill.TOOLS_OF_THE_TRADE,
            "rogue_fixture",
        ),
        (
            "button.test_user_defensive_stance",
            "cast_skill",
            Skill.DEFENSIVE_STANCE,
            "warrior_fixture",
        ),
        (
            "button.test_user_intimidating_gaze",
            "cast_skill",
            Skill.INTIMIDATING_GAZE,
            "warrior_fixture",
        ),
        (
            "button.test_user_valorous_presence",
            "cast_skill",
            Skill.VALOROUS_PRESENCE,
            "warrior_fixture",
        ),
        (
            "button.test_user_healing_light",
            "cast_skill",
            Skill.HEALING_LIGHT,
            "healer_fixture",
        ),
        (
            "button.test_user_protective_aura",
            "cast_skill",
            Skill.PROTECTIVE_AURA,
            "healer_fixture",
        ),
        (
            "button.test_user_searing_brightness",
            "cast_skill",
            Skill.SEARING_BRIGHTNESS,
            "healer_fixture",
        ),
        (
            "button.test_user_blessing",
            "cast_skill",
            Skill.BLESSING,
            "healer_fixture",
        ),
    ],
)
async def test_button_press(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    entity_id: str,
    call_func: str,
    call_args: Skill | None,
    fixture: str,
) -> None:
    """Test button press method."""

    habitica.get_user.return_value = HabiticaUserResponse.from_json(
        load_fixture(f"{fixture}.json", DOMAIN)
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mocked = getattr(habitica, call_func)
    mocked.reset_mock()
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    if call_args:
        mocked.assert_awaited_once_with(call_args)
    else:
        mocked.assert_awaited_once()


@pytest.mark.parametrize(
    ("entity_id", "call_func"),
    [
        ("button.test_user_allocate_all_stat_points", "allocate_stat_points"),
        ("button.test_user_buy_a_health_potion", "buy_health_potion"),
        ("button.test_user_revive_from_death", "revive"),
        ("button.test_user_start_my_day", "run_cron"),
        ("button.test_user_chilling_frost", "cast_skill"),
        ("button.test_user_earthquake", "cast_skill"),
        ("button.test_user_ethereal_surge", "cast_skill"),
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
    ("raise_exception", "msg", "expected_exception"),
    [
        (
            ERROR_TOO_MANY_REQUESTS,
            "Rate limit exceeded, try again later",
            HomeAssistantError,
        ),
        (
            ERROR_BAD_REQUEST,
            "Unable to connect to Habitica, try again later",
            HomeAssistantError,
        ),
        (
            ERROR_NOT_AUTHORIZED,
            "Unable to complete action, the required conditions are not met",
            ServiceValidationError,
        ),
    ],
)
async def test_button_press_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    entity_id: str,
    call_func: str,
    raise_exception: Exception,
    msg: str,
    expected_exception: Exception,
) -> None:
    """Test button press exceptions."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    func = getattr(habitica, call_func)
    func.side_effect = raise_exception

    with pytest.raises(expected_exception, match=msg):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


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
    habitica: AsyncMock,
    fixture: str,
    entity_ids: list[str],
) -> None:
    """Test buttons are unavailable if conditions are not met."""

    habitica.get_user.return_value = HabiticaUserResponse.from_json(
        load_fixture(f"{fixture}.json", DOMAIN)
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    for entity_id in entity_ids:
        assert (state := hass.states.get(entity_id))
        assert state.state == STATE_UNAVAILABLE


async def test_class_change(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test removing and adding skills after class change."""
    mage_skills = [
        "button.test_user_chilling_frost",
        "button.test_user_earthquake",
        "button.test_user_ethereal_surge",
    ]
    healer_skills = [
        "button.test_user_healing_light",
        "button.test_user_protective_aura",
        "button.test_user_searing_brightness",
        "button.test_user_blessing",
    ]

    habitica.get_user.return_value = HabiticaUserResponse.from_json(
        load_fixture("wizard_fixture.json", DOMAIN)
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    for skill in mage_skills:
        assert hass.states.get(skill)

    habitica.get_user.return_value = HabiticaUserResponse.from_json(
        load_fixture("healer_fixture.json", DOMAIN)
    )
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    for skill in mage_skills:
        assert not hass.states.get(skill)

    for skill in healer_skills:
        assert hass.states.get(skill)
