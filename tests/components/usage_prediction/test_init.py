"""Test usage_prediction integration."""

import asyncio
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.usage_prediction import get_cached_common_control
from homeassistant.components.usage_prediction.models import EntityUsagePredictions
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.mark.usefixtures("recorder_mock")
async def test_usage_prediction_caching(hass: HomeAssistant) -> None:
    """Test that usage prediction results are cached for 24 hours."""

    assert await async_setup_component(hass, "usage_prediction", {})

    prediction_mock = asyncio.Future()
    results = EntityUsagePredictions(
        morning=["light.kitchen"],
        afternoon=["climate.thermostat"],
        evening=["light.bedroom"],
        night=["lock.front_door"],
    )

    with patch(
        "homeassistant.components.usage_prediction.common_control.async_predict_common_control",
        Mock(return_value=prediction_mock),
    ):
        # First call, should trigger prediction
        task1 = asyncio.create_task(get_cached_common_control(hass, "user_1"))
        task2 = asyncio.create_task(get_cached_common_control(hass, "user_1"))

        prediction_mock.set_result(results)
        assert await task2 is results
        assert await task1 is results
