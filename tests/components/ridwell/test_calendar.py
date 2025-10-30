"""Test Ridwell calendar platform."""

from datetime import date

from aioridwell.model import EventState, RidwellPickup, RidwellPickupEvent
import pytest

from homeassistant.components.calendar import CalendarEvent
from homeassistant.components.ridwell.calendar import (
    async_get_calendar_event_from_pickup_event,
)
from homeassistant.components.ridwell.const import (
    CALENDAR_TITLE_NONE,
    CALENDAR_TITLE_ROTATING,
    CALENDAR_TITLE_STATUS,
    CONF_CALENDAR_TITLE,
)
from homeassistant.core import HomeAssistant

START_DATE = date(2025, 10, 4)
END_DATE = date(2025, 10, 5)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "pickup_name",
        "event_state",
        "summary_style",
        "expected_description",
        "expected_summary",
    ),
    [
        # Valid events that should be converted.
        # Pickup name of "Cork" is used to produce PickupCategory.ROTATING,
        # and "Plastic Film" is used to generate a PickupCategory.STANDARD pickup.
        (
            "Cork",
            EventState.SCHEDULED,
            CALENDAR_TITLE_ROTATING,  # Display Rotating Category in summary.
            "Pickup types: Cork (quantity: 1)",
            "Ridwell Pickup (Cork)",
        ),
        (
            "Cork",
            EventState.SCHEDULED,
            CALENDAR_TITLE_NONE,  # Display no extra info in summary.
            "Pickup types: Cork (quantity: 1)",
            "Ridwell Pickup",
        ),
        (
            "Cork",
            EventState.INITIALIZED,
            CALENDAR_TITLE_ROTATING,  # Display Rotating Category in summary.
            "Pickup types: Cork (quantity: 1)",
            "Ridwell Pickup (Cork)",
        ),
        (
            "Cork",
            EventState.SKIPPED,
            CALENDAR_TITLE_STATUS,  # Display pickup state in summary.
            "Pickup types: Cork (quantity: 1)",
            "Ridwell Pickup (skipped)",
        ),
        (
            "Cork",
            EventState.INITIALIZED,
            CALENDAR_TITLE_STATUS,  # Display pickup state in summary.
            "Pickup types: Cork (quantity: 1)",
            "Ridwell Pickup (initialized)",
        ),
        (
            "Cork",
            EventState.UNKNOWN,
            CALENDAR_TITLE_STATUS,  # Display pickup state in summary.
            "Pickup types: Cork (quantity: 1)",
            "Ridwell Pickup (unknown)",
        ),
    ],
)
async def test_calendar_event_varied_states_and_types(
    hass: HomeAssistant,
    config_entry,
    pickup_name: str,
    event_state: EventState,
    expected_description: str,
    expected_summary: str,
    summary_style: str,
) -> None:
    """Test CalendarEvent output based on pickup type and event state."""

    # Set calendar config to default
    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_CALENDAR_TITLE: summary_style},
    )
    await hass.async_block_till_done()

    # Create test pickup
    pickup = RidwellPickup(
        name=pickup_name,
        offer_id=f"offer_{pickup_name.lower()}",
        quantity=1,
        product_id=f"product_{pickup_name.lower()}",
        priority=1,
    )

    # Create test pickup event with the given state
    pickup_event = RidwellPickupEvent(
        _async_request=None,
        event_id=f"event_{pickup_name.lower()}_{event_state.name.lower()}",
        pickup_date=START_DATE,
        pickups=[pickup],
        state=event_state,
    )

    # Call the function under test
    event = async_get_calendar_event_from_pickup_event(pickup_event, config_entry)

    assert isinstance(event, CalendarEvent)
    assert event.summary == expected_summary
    assert event.description == expected_description
    assert event.start == START_DATE
    assert event.end == END_DATE


async def test_calendar_event_with_no_pickups(
    hass: HomeAssistant,
    config_entry,
) -> None:
    """Test empty pickups."""
    pickup_event = RidwellPickupEvent(
        _async_request=None,
        event_id="event_empty",
        pickup_date=START_DATE,
        pickups=[],
        state=EventState.SCHEDULED,
    )

    event = async_get_calendar_event_from_pickup_event(pickup_event, config_entry)
    assert event.description == "Pickup types: "
