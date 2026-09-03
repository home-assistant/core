"""Tests for the Famn sensor platform."""

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry

pytestmark = [pytest.mark.usefixtures("mock_famn")]


async def test_due_today_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the per-list and space-wide due-today sensors."""
    # 05:00 local (US/Pacific); the local day ends 2026-08-13T07:00:00Z.
    await hass.config.async_set_time_zone("US/Pacific")
    freezer.move_to("2026-08-12T12:00:00Z")
    await setup_integration(hass, mock_config_entry)

    # "Take out the trash" occurs 18:00Z today; "Vacuum the living room" is
    # due tomorrow (local); the other lists have no deadlines.
    weekly = hass.states.get("sensor.home_assistant_weekly_chores_due_today")
    assert weekly is not None
    assert weekly.state == "1"
    assert weekly.attributes["overdue"] == 0
    assert weekly.attributes["open_items"] == 2

    garden = hass.states.get("sensor.home_assistant_garden_due_today")
    assert garden is not None
    assert garden.state == "0"
    assert garden.attributes["open_items"] == 1

    total = hass.states.get("sensor.home_assistant_tasks_due_today")
    assert total is not None
    assert total.state == "1"
    assert total.attributes["overdue"] == 0
    assert total.attributes["open_items"] == 4


async def test_member_xp_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the per-member XP sensors built from the leaderboard."""
    freezer.move_to("2026-08-12T12:00:00Z")
    await setup_integration(hass, mock_config_entry)

    emma = hass.states.get("sensor.home_assistant_emma_xp")
    assert emma is not None
    assert emma.state == "120"
    assert emma.attributes["rank"] == 1
    assert emma.attributes["chores_completed"] == 14
    assert emma.attributes["current_streak_days"] == 5

    jonas = hass.states.get("sensor.home_assistant_jonas_xp")
    assert jonas is not None
    assert jonas.state == "85"
    assert jonas.attributes["rank"] == 2


async def test_dinner_tonight_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the dinner sensor shows tonight's planned meal."""
    freezer.move_to("2026-08-12T12:00:00Z")
    await setup_integration(hass, mock_config_entry)

    dinner = hass.states.get("sensor.home_assistant_dinner_tonight")
    assert dinner is not None
    assert dinner.state == "Taco"
    assert dinner.attributes["status"] == "planned"
    assert dinner.attributes["servings"] == 4
    assert dinner.attributes["prep_time"] == 20
    # Famn stores the Cloudflare Images base URL; the variant suffix makes
    # it renderable.
    assert dinner.attributes["entity_picture"] == (
        "https://imagedelivery.net/YOVIzOVFuBiBBmJn2AVFiw/"
        "c430f99a-310c-4917-5a8e-db7328c04700/public"
    )


async def test_dinner_tonight_without_plan(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the dinner sensor is unknown on a day without a plan."""
    freezer.move_to("2026-08-20T12:00:00Z")
    await setup_integration(hass, mock_config_entry)

    dinner = hass.states.get("sensor.home_assistant_dinner_tonight")
    assert dinner is not None
    assert dinner.state == "unknown"


async def test_overdue_counts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that overdue items count as both overdue and due today."""
    # Two days later everything with a deadline is overdue.
    freezer.move_to("2026-08-14T12:00:00Z")
    await setup_integration(hass, mock_config_entry)

    weekly = hass.states.get("sensor.home_assistant_weekly_chores_due_today")
    assert weekly is not None
    assert weekly.state == "2"
    assert weekly.attributes["overdue"] == 2

    total = hass.states.get("sensor.home_assistant_tasks_due_today")
    assert total is not None
    assert total.state == "2"
    assert total.attributes["overdue"] == 2


async def test_xp_sensor_for_member_without_xp(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that a member who is absent from the leaderboard still gets a sensor.

    Famn's seasons reset weekly and drop everyone on zero from the
    leaderboard, so the roster is what decides which sensors exist.
    """
    await setup_integration(hass, mock_config_entry)

    # Bestemor is on the roster but has earned nothing this season.
    bestemor = hass.states.get("sensor.home_assistant_bestemor_xp")
    assert bestemor is not None
    assert bestemor.state == "0"
