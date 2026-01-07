"""Test usage_prediction integration."""

import asyncio
from unittest.mock import patch

import pytest

from homeassistant.components.usage_prediction import get_cached_common_control
from homeassistant.components.usage_prediction.models import EntityUsagePredictions
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.mark.usefixtures("recorder_mock")
async def test_usage_prediction_caching(hass: HomeAssistant) -> None:
    """Test that usage prediction results are cached for 24 hours."""

    assert await async_setup_component(hass, "usage_prediction", {})

    finish_event = asyncio.Event()

    async def mock_common_control_error(*args) -> EntityUsagePredictions:
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
    results = EntityUsagePredictions(
        morning=["light.kitchen"],
        afternoon=["climate.thermostat"],
        evening=["light.bedroom"],
        night=["lock.front_door"],
    )

    # The exception is not cached, we hit the method again.
    async def mock_common_control(*args) -> EntityUsagePredictions:
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
