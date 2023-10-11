"""Tests for the Epic Games Store calendars."""

from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.calendar import DOMAIN as CALENDAR_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .common import setup_platform

from tests.common import async_fire_time_changed


async def test_setup_component(hass: HomeAssistant, service_multiple: Mock) -> None:
    """Test setup component with calendars."""
    await setup_platform(hass, CALENDAR_DOMAIN)

    state = hass.states.get("calendar.epic_games_store_discount_games")
    assert state.name == "Epic Games Store Discount games"
    state = hass.states.get("calendar.epic_games_store_free_games")
    assert state.name == "Epic Games Store Free games"


async def test_discount_games(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    service_multiple: Mock,
) -> None:
    """Test setup component with calendars."""
    freezer.move_to("2022-10-15T00:00:00.000Z")

    await setup_platform(hass, CALENDAR_DOMAIN)

    state = hass.states.get("calendar.epic_games_store_discount_games")
    assert state.state == STATE_OFF

    freezer.move_to("2022-10-30T00:00:00.000Z")
    async_fire_time_changed(hass)

    state = hass.states.get("calendar.epic_games_store_discount_games")
    assert state.state == STATE_ON

    cal_attrs = dict(state.attributes)
    cal_games = cal_attrs.pop("games")
    assert cal_attrs == {
        "friendly_name": "Epic Games Store Discount games",
        "message": "Shadow of the Tomb Raider: Definitive Edition",
        "all_day": False,
        "start_time": "2022-10-18 08:00:00",
        "end_time": "2022-11-01 08:00:00",
        "location": "",
        "description": "In Shadow of the Tomb Raider Definitive Edition experience the final chapter of Lara\u2019s origin as she is forged into the Tomb Raider she is destined to be.\n\nhttps://store.epicgames.com/fr/p/shadow-of-the-tomb-raider",
    }
    assert [cal_game["title"] for cal_game in cal_games] == [
        "Shadow of the Tomb Raider: Definitive Edition",
        "Terraforming Mars",
        "A Game Of Thrones: The Board Game Digital Edition",
        "Fallout 3: Game of the Year Edition",
    ]


async def test_free_games(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    service_multiple: Mock,
) -> None:
    """Test setup component with calendars."""
    freezer.move_to("2022-10-30T00:00:00.000Z")

    await setup_platform(hass, CALENDAR_DOMAIN)

    state = hass.states.get("calendar.epic_games_store_free_games")
    assert state.state == STATE_ON

    cal_attrs = dict(state.attributes)
    cal_games = cal_attrs.pop("games")
    assert cal_attrs == {
        "friendly_name": "Epic Games Store Free games",
        "message": "Warhammer 40,000: Mechanicus - Standard Edition",
        "all_day": False,
        "start_time": "2022-10-27 08:00:00",
        "end_time": "2022-11-03 08:00:00",
        "location": "",
        "description": "Take control of the most technologically advanced army in the Imperium - The Adeptus Mechanicus. Your every decision will weigh heavily on the outcome of the mission, in this turn-based tactical game. Will you be blessed by the Omnissiah?\n\nhttps://store.epicgames.com/fr/p/warhammer-mechanicus-0e4b71",
    }
    assert [cal_game["title"] for cal_game in cal_games] == [
        "Warhammer 40,000: Mechanicus - Standard Edition",
        "Saturnalia",
        "Rising Storm 2: Vietnam",
        "Filament",
    ]


async def test_attribute_not_found(
    hass: HomeAssistant, service_attribute_not_found: Mock
) -> None:
    """Test setup component with calendars."""
    await setup_platform(hass, CALENDAR_DOMAIN)

    state = hass.states.get("calendar.epic_games_store_discount_games")
    assert state.name == "Epic Games Store Discount games"
    state = hass.states.get("calendar.epic_games_store_free_games")
    assert state.name == "Epic Games Store Free games"
    assert state.state == STATE_ON
    cal_attrs = dict(state.attributes)
    cal_games = cal_attrs.pop("games")
    assert len(cal_games) == 3
