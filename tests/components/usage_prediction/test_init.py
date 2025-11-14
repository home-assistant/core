"""Test usage_prediction integration."""

import asyncio
from unittest.mock import patch

import pytest

from homeassistant.components.usage_prediction import (
    get_cached_common_control,
    get_predictions_for_location,
)
from homeassistant.components.usage_prediction.models import (
    EntityUsagePredictions,
    LocationBasedPredictions,
)
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.mark.usefixtures("recorder_mock")
async def test_usage_prediction_caching(hass: HomeAssistant) -> None:
    """Test that usage prediction results are cached for 24 hours."""

    assert await async_setup_component(hass, "usage_prediction", {})

    finish_event = asyncio.Event()

    async def mock_common_control_error(*args) -> LocationBasedPredictions:
        await finish_event.wait()
        raise Exception("Boom")  # noqa: TRY002

    with patch(
        "homeassistant.components.usage_prediction.common_control.async_predict_common_control",
        mock_common_control_error,
    ):
        # First call, should trigger prediction
        task1 = asyncio.create_task(get_cached_common_control(hass, "user_1"))
        task2 = asyncio.create_task(get_cached_common_control(hass, "user_1"))
        await asyncio.sleep(0)
        finish_event.set()
        with pytest.raises(Exception, match="Boom"):
            await task2
        with pytest.raises(Exception, match="Boom"):
            await task1

    finish_event.clear()
    results = LocationBasedPredictions(
        location_predictions={
            STATE_HOME: EntityUsagePredictions(
                morning=["light.kitchen"],
                afternoon=["climate.thermostat"],
                evening=["light.bedroom"],
                night=["lock.front_door"],
            )
        }
    )

    # The exception is not cached, we hit the method again.
    async def mock_common_control(*args) -> LocationBasedPredictions:
        await finish_event.wait()
        return results

    with patch(
        "homeassistant.components.usage_prediction.common_control.async_predict_common_control",
        mock_common_control,
    ):
        # First call, should trigger prediction
        task1 = asyncio.create_task(get_cached_common_control(hass, "user_1"))
        task2 = asyncio.create_task(get_cached_common_control(hass, "user_1"))
        await asyncio.sleep(0)
        finish_event.set()
        assert await task2 is results
        assert await task1 is results


def test_fallback_logic_returns_specific_location() -> None:
    """Test fallback returns predictions for specific location when available."""
    predictions = LocationBasedPredictions(
        location_predictions={
            "work": EntityUsagePredictions(
                morning=["light.work"],
                afternoon=["climate.work"],
                evening=[],
                night=[],
            ),
            STATE_HOME: EntityUsagePredictions(
                morning=["light.home"],
                afternoon=["climate.home"],
                evening=[],
                night=[],
            ),
        }
    )

    result = get_predictions_for_location(predictions, "work")
    assert result.morning == ["light.work"]
    assert result.afternoon == ["climate.work"]


def test_fallback_logic_custom_zone_to_not_home() -> None:
    """Test fallback from custom zone to not_home when custom zone has no results."""
    predictions = LocationBasedPredictions(
        location_predictions={
            "work": EntityUsagePredictions(
                morning=[],
                afternoon=[],
                evening=[],
                night=[],
            ),
            STATE_NOT_HOME: EntityUsagePredictions(
                morning=["light.away"],
                afternoon=["climate.away"],
                evening=[],
                night=[],
            ),
            STATE_HOME: EntityUsagePredictions(
                morning=["light.home"],
                afternoon=["climate.home"],
                evening=[],
                night=[],
            ),
        }
    )

    result = get_predictions_for_location(predictions, "work")
    # Should fall back to not_home
    assert result.morning == ["light.away"]
    assert result.afternoon == ["climate.away"]


def test_fallback_logic_custom_zone_to_home() -> None:
    """Test fallback from custom zone to home when not_home has no results."""
    predictions = LocationBasedPredictions(
        location_predictions={
            "gym": EntityUsagePredictions(
                morning=[],
                afternoon=[],
                evening=[],
                night=[],
            ),
            STATE_NOT_HOME: EntityUsagePredictions(
                morning=[],
                afternoon=[],
                evening=[],
                night=[],
            ),
            STATE_HOME: EntityUsagePredictions(
                morning=["light.home"],
                afternoon=["climate.home"],
                evening=[],
                night=[],
            ),
        }
    )

    result = get_predictions_for_location(predictions, "gym")
    # Should fall back to home
    assert result.morning == ["light.home"]
    assert result.afternoon == ["climate.home"]


def test_fallback_logic_no_location_data() -> None:
    """Test fallback returns empty when custom zone not in predictions."""
    predictions = LocationBasedPredictions(
        location_predictions={
            STATE_HOME: EntityUsagePredictions(
                morning=["light.home"],
                afternoon=["climate.home"],
                evening=[],
                night=[],
            ),
        }
    )

    result = get_predictions_for_location(predictions, "unknown_zone")
    # Should fall back to home
    assert result.morning == ["light.home"]
    assert result.afternoon == ["climate.home"]


def test_fallback_logic_empty_predictions() -> None:
    """Test fallback returns empty when no predictions available."""
    predictions = LocationBasedPredictions(location_predictions={})

    result = get_predictions_for_location(predictions, "work")
    # Should return empty predictions
    assert result.morning == []
    assert result.afternoon == []
    assert result.evening == []
    assert result.night == []


def test_no_fallback_for_home_or_not_home() -> None:
    """Test that home and not_home states don't fall back."""
    predictions = LocationBasedPredictions(
        location_predictions={
            STATE_HOME: EntityUsagePredictions(
                morning=["light.home"],
                afternoon=[],
                evening=[],
                night=[],
            ),
        }
    )

    # not_home should return empty, not fall back to home
    result = get_predictions_for_location(predictions, STATE_NOT_HOME)
    assert result.morning == []
    assert result.afternoon == []
    assert result.evening == []
    assert result.night == []
