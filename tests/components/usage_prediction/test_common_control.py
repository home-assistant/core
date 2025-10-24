"""Test the common control usage prediction."""

from __future__ import annotations

from unittest.mock import patch
import uuid

from freezegun import freeze_time
import pytest

from homeassistant.components.usage_prediction.common_control import (
    async_predict_common_control,
    time_category,
)
from homeassistant.components.usage_prediction.models import EntityUsagePredictions
from homeassistant.const import EVENT_CALL_SERVICE
from homeassistant.core import Context, HomeAssistant

from tests.components.recorder.common import async_wait_recording_done


def test_time_category() -> None:
    """Test the time category calculation logic."""
    for hour in range(6):
        assert time_category(hour) == "night", hour
    for hour in range(7, 12):
        assert time_category(hour) == "morning", hour
    for hour in range(13, 18):
        assert time_category(hour) == "afternoon", hour
    for hour in range(19, 22):
        assert time_category(hour) == "evening", hour


@pytest.mark.usefixtures("recorder_mock")
async def test_empty_database(hass: HomeAssistant) -> None:
    """Test function with empty database returns empty results."""
    user_id = str(uuid.uuid4())

    # Call the function with empty database
    results = await async_predict_common_control(hass, user_id)

    # Should return empty lists for all time categories
    assert results == EntityUsagePredictions(
        morning=[],
        afternoon=[],
        evening=[],
        night=[],
    )


@pytest.mark.usefixtures("recorder_mock")
async def test_invalid_user_id(hass: HomeAssistant) -> None:
    """Test function with invalid user ID returns empty results."""
    # Invalid user ID format (not a valid UUID)
    with pytest.raises(ValueError, match=r"Invalid user_id format"):
        await async_predict_common_control(hass, "invalid-user-id")


@pytest.mark.usefixtures("recorder_mock")
async def test_with_service_calls(hass: HomeAssistant) -> None:
    """Test function with actual service call events in database."""
    user_id = str(uuid.uuid4())

    # Create service call events at different times of day
    # Morning events - use separate service calls to get around context deduplication
    with freeze_time("2023-07-01 07:00:00+00:00"):  # Morning
        hass.bus.async_fire(
            EVENT_CALL_SERVICE,
            {
                "domain": "light",
                "service": "turn_on",
                "service_data": {"entity_id": ["light.living_room", "light.kitchen"]},
            },
            context=Context(user_id=user_id),
        )
        await hass.async_block_till_done()

    # Afternoon events
    with freeze_time("2023-07-01 14:00:00+00:00"):  # Afternoon
        hass.bus.async_fire(
            EVENT_CALL_SERVICE,
            {
                "domain": "climate",
                "service": "set_temperature",
                "service_data": {"entity_id": "climate.thermostat"},
            },
            context=Context(user_id=user_id),
        )
        await hass.async_block_till_done()

    # Evening events
    with freeze_time("2023-07-01 19:00:00+00:00"):  # Evening
        hass.bus.async_fire(
            EVENT_CALL_SERVICE,
            {
                "domain": "light",
                "service": "turn_off",
                "service_data": {"entity_id": "light.bedroom"},
            },
            context=Context(user_id=user_id),
        )
        await hass.async_block_till_done()

    # Night events
    with freeze_time("2023-07-01 23:00:00+00:00"):  # Night
        hass.bus.async_fire(
            EVENT_CALL_SERVICE,
            {
                "domain": "lock",
                "service": "lock",
                "service_data": {"entity_id": "lock.front_door"},
            },
            context=Context(user_id=user_id),
        )
        await hass.async_block_till_done()

    # Wait for events to be recorded
    await async_wait_recording_done(hass)

    # Get predictions - make sure we're still in a reasonable timeframe
    with freeze_time("2023-07-02 10:00:00+00:00"):  # Next day, so events are recent
        results = await async_predict_common_control(hass, user_id)

    # Verify results contain the expected entities in the correct time periods
    assert results == EntityUsagePredictions(
        morning=["climate.thermostat"],
        afternoon=["light.bedroom", "lock.front_door"],
        evening=[],
        night=["light.living_room", "light.kitchen"],
    )


@pytest.mark.usefixtures("recorder_mock")
async def test_multiple_entities_in_one_call(hass: HomeAssistant) -> None:
    """Test handling of service calls with multiple entity IDs."""
    user_id = str(uuid.uuid4())

    with freeze_time("2023-07-01 10:00:00+00:00"):  # Morning
        hass.bus.async_fire(
            EVENT_CALL_SERVICE,
            {
                "domain": "light",
                "service": "turn_on",
                "service_data": {
                    "entity_id": [
                        "light.living_room",
                        "light.kitchen",
                        "light.hallway",
                        "not_allowed.domain",
                    ]
                },
            },
            context=Context(user_id=user_id),
        )
        await hass.async_block_till_done()

    await async_wait_recording_done(hass)

    with freeze_time("2023-07-02 10:00:00+00:00"):  # Next day, so events are recent
        results = await async_predict_common_control(hass, user_id)

    # All three lights should be counted (10:00 UTC = 02:00 local = night)
    assert results.night == ["light.living_room", "light.kitchen", "light.hallway"]
    assert results.morning == []
    assert results.afternoon == []
    assert results.evening == []


@pytest.mark.usefixtures("recorder_mock")
async def test_context_deduplication(hass: HomeAssistant) -> None:
    """Test that multiple events with the same context are deduplicated."""
    user_id = str(uuid.uuid4())
    context = Context(user_id=user_id)

    with freeze_time("2023-07-01 10:00:00+00:00"):  # Morning
        # Fire multiple events with the same context
        hass.bus.async_fire(
            EVENT_CALL_SERVICE,
            {
                "domain": "light",
                "service": "turn_on",
                "service_data": {"entity_id": "light.living_room"},
            },
            context=context,
        )
        await hass.async_block_till_done()

        hass.bus.async_fire(
            EVENT_CALL_SERVICE,
            {
                "domain": "switch",
                "service": "turn_on",
                "service_data": {"entity_id": "switch.coffee_maker"},
            },
            context=context,  # Same context
        )
        await hass.async_block_till_done()

    await async_wait_recording_done(hass)

    with freeze_time("2023-07-02 10:00:00+00:00"):  # Next day, so events are recent
        results = await async_predict_common_control(hass, user_id)

    # Only the first event should be processed (10:00 UTC = 02:00 local = night)
    assert results == EntityUsagePredictions(
        morning=[],
        afternoon=[],
        evening=[],
        night=["light.living_room"],
    )


@pytest.mark.usefixtures("recorder_mock")
async def test_old_events_excluded(hass: HomeAssistant) -> None:
    """Test that events older than 30 days are excluded."""
    user_id = str(uuid.uuid4())

    # Create an old event (35 days ago)
    with freeze_time("2023-05-27 10:00:00+00:00"):  # 35 days before July 1st
        hass.bus.async_fire(
            EVENT_CALL_SERVICE,
            {
                "domain": "light",
                "service": "turn_on",
                "service_data": {"entity_id": "light.old_event"},
            },
            context=Context(user_id=user_id),
        )
        await hass.async_block_till_done()

    # Create a recent event (5 days ago)
    with freeze_time("2023-06-26 10:00:00+00:00"):  # 5 days before July 1st
        hass.bus.async_fire(
            EVENT_CALL_SERVICE,
            {
                "domain": "light",
                "service": "turn_on",
                "service_data": {"entity_id": "light.recent_event"},
            },
            context=Context(user_id=user_id),
        )
        await hass.async_block_till_done()

    await async_wait_recording_done(hass)

    # Query with current time
    with freeze_time("2023-07-01 10:00:00+00:00"):
        results = await async_predict_common_control(hass, user_id)

    # Only recent event should be included (10:00 UTC = 02:00 local = night)
    assert results == EntityUsagePredictions(
        morning=[],
        afternoon=[],
        evening=[],
        night=["light.recent_event"],
    )


@pytest.mark.usefixtures("recorder_mock")
async def test_entities_limit(hass: HomeAssistant) -> None:
    """Test that only top entities are returned per time category."""
    user_id = str(uuid.uuid4())

    # Create more than 5 different entities in morning
    with freeze_time("2023-07-01 08:00:00+00:00"):
        # Create entities with different frequencies
        entities_with_counts = [
            ("light.most_used", 10),
            ("light.second", 8),
            ("light.third", 6),
            ("light.fourth", 4),
            ("light.fifth", 2),
            ("light.sixth", 1),
            ("light.seventh", 1),
        ]

        for entity_id, count in entities_with_counts:
            for _ in range(count):
                # Use different context for each call
                hass.bus.async_fire(
                    EVENT_CALL_SERVICE,
                    {
                        "domain": "light",
                        "service": "toggle",
                        "service_data": {"entity_id": entity_id},
                    },
                    context=Context(user_id=user_id),
                )
                await hass.async_block_till_done()

    await async_wait_recording_done(hass)

    with (
        freeze_time("2023-07-02 10:00:00+00:00"),
        patch(
            "homeassistant.components.usage_prediction.common_control.RESULTS_TO_INCLUDE",
            5,
        ),
    ):  # Next day, so events are recent
        results = await async_predict_common_control(hass, user_id)

    # Should be the top 5 most used (08:00 UTC = 00:00 local = night)
    assert results.night == [
        "light.most_used",
        "light.second",
        "light.third",
        "light.fourth",
        "light.fifth",
    ]
    assert results.morning == []
    assert results.afternoon == []
    assert results.evening == []


@pytest.mark.usefixtures("recorder_mock")
async def test_different_users_separated(hass: HomeAssistant) -> None:
    """Test that events from different users are properly separated."""
    user_id_1 = str(uuid.uuid4())
    user_id_2 = str(uuid.uuid4())

    with freeze_time("2023-07-01 10:00:00+00:00"):
        # User 1 events
        hass.bus.async_fire(
            EVENT_CALL_SERVICE,
            {
                "domain": "light",
                "service": "turn_on",
                "service_data": {"entity_id": "light.user1_light"},
            },
            context=Context(user_id=user_id_1),
        )
        await hass.async_block_till_done()

        # User 2 events
        hass.bus.async_fire(
            EVENT_CALL_SERVICE,
            {
                "domain": "light",
                "service": "turn_on",
                "service_data": {"entity_id": "light.user2_light"},
            },
            context=Context(user_id=user_id_2),
        )
        await hass.async_block_till_done()

    await async_wait_recording_done(hass)

    # Get results for each user
    with freeze_time("2023-07-02 10:00:00+00:00"):  # Next day, so events are recent
        results_user1 = await async_predict_common_control(hass, user_id_1)
        results_user2 = await async_predict_common_control(hass, user_id_2)

    # Each user should only see their own entities (10:00 UTC = 02:00 local = night)
    assert results_user1 == EntityUsagePredictions(
        morning=[],
        afternoon=[],
        evening=[],
        night=["light.user1_light"],
    )

    assert results_user2 == EntityUsagePredictions(
        morning=[],
        afternoon=[],
        evening=[],
        night=["light.user2_light"],
    )
