"""Tests for the Culiplan calendar entity."""

from datetime import UTC, datetime

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def _slot(date_iso: str, **extra: object) -> dict[str, object]:
    """Return a meal-plan slot stub."""
    base = {
        "id": "slot",
        "date": date_iso,
        "title": "Spaghetti",
        "recipeId": "r1",
        "course": "dinner",
        "servings": 2,
    }
    base.update(extra)
    return base


async def test_calendar_entity_state_and_events(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """The calendar entity surfaces the upcoming event."""
    coordinator = setup_integration.runtime_data.coordinator
    # Use a far-future date so the calendar's current/next event is always
    # this one regardless of when the test runs.
    coordinator.async_set_updated_data(
        {
            "meal_plans": [
                {
                    "id": "current",
                    "name": "Meal Plan",
                    "slots": [
                        _slot("2199-01-15T18:00:00Z", id="s1"),
                        _slot("not-a-date", id="s3"),  # malformed → logged & skipped
                    ],
                }
            ],
            "shopping_lists": [],
            "pantry_items": [],
        }
    )
    await hass.async_block_till_done()
    state = hass.states.get("calendar.culiplan_meal_plan")
    assert state is not None
    assert state.attributes["recipe_id"] == "r1"


async def test_calendar_async_get_events(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """`async_get_events` returns events in the requested window."""
    coordinator = setup_integration.runtime_data.coordinator
    coordinator.async_set_updated_data(
        {
            "meal_plans": [
                {
                    "id": "current",
                    "name": "Meal Plan",
                    "slots": [_slot("2199-01-15T18:00:00Z", id="s1")],
                }
            ],
            "shopping_lists": [],
            "pantry_items": [],
        }
    )
    await hass.async_block_till_done()
    entity_id = "calendar.culiplan_meal_plan"
    res = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "entity_id": entity_id,
            "start_date_time": datetime(2199, 1, 14, tzinfo=UTC),
            "end_date_time": datetime(2199, 1, 16, tzinfo=UTC),
        },
        blocking=True,
        return_response=True,
    )
    events = res[entity_id]["events"]
    assert len(events) == 1
    assert events[0]["summary"] == "Spaghetti"
