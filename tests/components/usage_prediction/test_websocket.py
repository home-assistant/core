"""Test usage_prediction WebSocket API."""

from collections.abc import Generator
from copy import deepcopy
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from freezegun import freeze_time
import pytest

from homeassistant.components.usage_prediction.models import EntityUsagePredictions
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockUser
from tests.typing import WebSocketGenerator

NOW = datetime(2026, 8, 26, 15, 0, 0, tzinfo=dt_util.UTC)


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
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
    mock_predict_common_control: Mock,
) -> None:
    """Test usage_prediction common control WebSocket command."""
    assert await async_setup_component(hass, "usage_prediction", {})

    client = await hass_ws_client(hass)

    with freeze_time(NOW):
        await client.send_json({"id": 1, "type": "usage_prediction/common_control"})
        msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["type"] == "result"
    assert msg["success"] is True
    assert msg["result"] == {
        "entities": [
            "light.kitchen",
        ]
    }
    assert mock_predict_common_control.call_count == 1
    assert mock_predict_common_control.mock_calls[0][1][1] == hass_admin_user.id


@pytest.mark.usefixtures("recorder_mock")
async def test_caching_behavior(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_predict_common_control: Mock,
) -> None:
    """Test that results are cached for 24 hours."""
    assert await async_setup_component(hass, "usage_prediction", {})

    client = await hass_ws_client(hass)

    # First call should fetch from database
    with freeze_time(NOW):
        await client.send_json({"id": 1, "type": "usage_prediction/common_control"})
        msg = await client.receive_json()

    assert msg["success"] is True
    assert msg["result"] == {
        "entities": [
            "light.kitchen",
        ]
    }
    assert mock_predict_common_control.call_count == 1

    new_result = deepcopy(mock_predict_common_control.return_value)
    new_result.morning.append("light.bla")
    mock_predict_common_control.return_value = new_result

    # Second call within 24 hours should use cache
    with freeze_time(NOW + timedelta(hours=23)):
        await client.send_json({"id": 2, "type": "usage_prediction/common_control"})
        msg = await client.receive_json()

    assert msg["success"] is True
    assert msg["result"] == {
        "entities": [
            "light.kitchen",
        ]
    }
    # Should still be 1 (no new database call)
    assert mock_predict_common_control.call_count == 1

    # Third call after 24 hours should fetch from database again
    with freeze_time(NOW + timedelta(hours=25)):
        await client.send_json({"id": 3, "type": "usage_prediction/common_control"})
        msg = await client.receive_json()

    assert msg["success"] is True
    assert msg["result"] == {"entities": ["light.kitchen", "light.bla"]}
    # Should now be 2 (new database call)
    assert mock_predict_common_control.call_count == 2
