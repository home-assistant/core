"""Test usage_prediction HTTP API."""

import asyncio
from collections.abc import Generator
from copy import deepcopy
from datetime import timedelta
from http import HTTPStatus
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.usage_prediction.models import EntityUsagePredictions
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockUser
from tests.typing import ClientSessionGenerator

NOW = dt_util.utcnow().replace(hour=8, minute=0, second=0, microsecond=0)
# 08:00 UTC = morning time category (06:00-12:00)


@pytest.fixture
def mock_predict_common_control() -> Generator[Mock]:
    """Return a mock result for common control."""
    with patch(
        "homeassistant.components.usage_prediction.common_control.async_predict_common_control",
        return_value=EntityUsagePredictions(
            morning=["light.kitchen"],
            afternoon=["climate.thermostat"],
            evening=["light.bedroom"],
            night=["lock.front_door"],
        ),
    ) as mock_predict:
        yield mock_predict


@pytest.mark.usefixtures("recorder_mock")
async def test_common_control(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_admin_user: MockUser,
    mock_predict_common_control: Mock,
) -> None:
    """Test usage_prediction common control HTTP API."""
    assert await async_setup_component(hass, "usage_prediction", {})

    client = await hass_client()

    with patch("homeassistant.util.dt.now", return_value=NOW):
        resp = await client.get("/api/usage_prediction/common_control")

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data == {
        "entities": [
            "light.kitchen",
        ]
    }
    assert mock_predict_common_control.call_count == 1
    assert mock_predict_common_control.mock_calls[0][1][1] == hass_admin_user.id


@pytest.mark.usefixtures("recorder_mock")
async def test_caching_behavior(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_predict_common_control: Mock,
) -> None:
    """Test that results are cached for 24 hours."""
    assert await async_setup_component(hass, "usage_prediction", {})

    client = await hass_client()

    # First call should fetch from database
    with (
        patch("homeassistant.util.dt.now", return_value=NOW),
        patch("homeassistant.components.usage_prediction.models.dt_util.utcnow", return_value=NOW),
    ):
        resp = await client.get("/api/usage_prediction/common_control")

    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    assert data == {
        "entities": [
            "light.kitchen",
        ]
    }
    assert mock_predict_common_control.call_count == 1

    new_result = deepcopy(mock_predict_common_control.return_value)
    new_result.morning.append("light.bla")
    mock_predict_common_control.return_value = new_result

    # Second call within 24 hours should use cache
    with (
        patch("homeassistant.util.dt.now", return_value=NOW + timedelta(hours=23)),
        patch("homeassistant.components.usage_prediction.dt_util.utcnow", return_value=NOW + timedelta(hours=23)),
    ):
        resp = await client.get("/api/usage_prediction/common_control")

    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    assert data == {
        "entities": [
            "light.kitchen",
        ]
    }
    # Should still be 1 (no new database call)
    assert mock_predict_common_control.call_count == 1

    # Third call after 24 hours should fetch from database again
    # Clear the cache manually since time mocking doesn't work well with dataclass defaults
    hass.data["usage_prediction"] = {}

    with (
        patch("homeassistant.util.dt.now", return_value=NOW + timedelta(hours=25)),
        patch("homeassistant.components.usage_prediction.dt_util.utcnow", return_value=NOW + timedelta(hours=25)),
    ):
        resp = await client.get("/api/usage_prediction/common_control")

    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    assert data == {"entities": ["light.kitchen", "light.bla"]}
    # Should now be 2 (new database call)
    assert mock_predict_common_control.call_count == 2


@pytest.mark.usefixtures("recorder_mock")
async def test_concurrent_requests(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_predict_common_control: Mock,
) -> None:
    """Test that concurrent requests don't cause multiple database calls."""
    assert await async_setup_component(hass, "usage_prediction", {})

    client = await hass_client()

    # Make multiple concurrent requests
    with patch("homeassistant.util.dt.now", return_value=NOW):
        responses = await asyncio.gather(
            client.get("/api/usage_prediction/common_control"),
            client.get("/api/usage_prediction/common_control"),
            client.get("/api/usage_prediction/common_control"),
        )

    # All requests should succeed
    for resp in responses:
        assert resp.status == HTTPStatus.OK
        data = await resp.json()
        assert data == {"entities": ["light.kitchen"]}

    # Should only call the prediction function once due to task caching
    assert mock_predict_common_control.call_count == 1


@pytest.mark.usefixtures("recorder_mock")
async def test_prediction_error_handling(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that prediction errors are handled gracefully."""
    assert await async_setup_component(hass, "usage_prediction", {})

    client = await hass_client()

    # Mock the prediction function to raise an exception
    with (
        patch(
            "homeassistant.components.usage_prediction.common_control.async_predict_common_control",
            side_effect=Exception("Database error"),
        ) as mock_predict,
        patch("homeassistant.util.dt.now", return_value=NOW),
    ):
        resp = await client.get("/api/usage_prediction/common_control")

    # The error should bubble up as a 500 error
    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert mock_predict.call_count == 1

    # Verify cache was cleared so next request can retry
    assert hass.data["usage_prediction"] == {}
