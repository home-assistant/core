"""Tests for the Epic Games Store calendars."""

from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.calendar import DOMAIN as CALENDAR_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .common import setup_platform


async def test_setup_component(hass: HomeAssistant, service_multiple: Mock) -> None:
    """Test setup component with calendars."""
    await setup_platform(hass, CALENDAR_DOMAIN)

    state = hass.states.get("calendar.epic_games_store_discount_games")
    assert state.name == "Epic Games Store Discount Games"
    state = hass.states.get("calendar.epic_games_store_free_games")
    assert state.name == "Epic Games Store Free Games"


async def test_discount_games(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    service_multiple: Mock,
) -> None:
    """Test setup component with calendars."""
    freezer.move_to("2022-11-01T15:00:00.000Z")

    await setup_platform(hass, CALENDAR_DOMAIN)

    state = hass.states.get("calendar.epic_games_store_discount_games")
    assert state.state == STATE_OFF
    cal_attrs = dict(state.attributes)
    cal_games = cal_attrs.pop("games")
    assert cal_attrs == {
        "friendly_name": "Epic Games Store Discount Games",
    }
    assert len(cal_games) == 0


async def test_free_games(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    service_multiple: Mock,
) -> None:
    """Test setup component with calendars."""
    freezer.move_to("2022-11-01T15:00:00.000Z")

    await setup_platform(hass, CALENDAR_DOMAIN)

    state = hass.states.get("calendar.epic_games_store_free_games")
    assert state.state == STATE_ON
    cal_attrs = dict(state.attributes)
    cal_games = cal_attrs.pop("games")
    assert cal_attrs == {
        "friendly_name": "Epic Games Store Free Games",
        "message": "Warhammer 40,000: Mechanicus - Standard Edition",
        "all_day": False,
        "start_time": "2022-10-27 08:00:00",
        "end_time": "2022-11-03 08:00:00",
        "location": "",
        "description": "Take control of the most technologically advanced army in the Imperium - The Adeptus Mechanicus. Your every decision will weigh heavily on the outcome of the mission, in this turn-based tactical game. Will you be blessed by the Omnissiah?\n\nhttps://store.epicgames.com/fr/p/warhammer-mechanicus-0e4b71",
    }
    assert len(cal_games) == 4
