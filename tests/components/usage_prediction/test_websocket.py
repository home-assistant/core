"""Test usage_prediction WebSocket API."""

from collections.abc import Generator
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import Mock, patch

from freezegun import freeze_time
import pytest

from homeassistant.components.usage_prediction import DOMAIN
from homeassistant.components.usage_prediction.const import (
    DEFAULT_NUM_RESULTS,
    MAX_NUM_RESULTS,
)
from homeassistant.components.usage_prediction.models import EntityUsagePredictions
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockUser
from tests.typing import WebSocketGenerator

NOW = datetime(2026, 8, 26, 15, 0, 0, tzinfo=dt_util.UTC)

MORNING_ENTITIES = [f"light.morning_{index}" for index in range(MAX_NUM_RESULTS + 10)]


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
    assert await async_setup_component(hass, DOMAIN, {})

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
    assert await async_setup_component(hass, DOMAIN, {})

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


@pytest.mark.usefixtures("recorder_mock")
@pytest.mark.parametrize(
    ("extra_msg", "expected_entities"),
    [
        pytest.param({}, MORNING_ENTITIES[:DEFAULT_NUM_RESULTS], id="default"),
        pytest.param({"num_results": 3}, MORNING_ENTITIES[:3], id="fewer"),
        pytest.param(
            {"num_results": MAX_NUM_RESULTS + 100},
            MORNING_ENTITIES[:MAX_NUM_RESULTS],
            id="clamped_to_maximum",
        ),
        pytest.param({"num_results": 0}, MORNING_ENTITIES[:1], id="clamped_to_minimum"),
    ],
)
async def test_common_control_num_results(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    extra_msg: dict[str, Any],
    expected_entities: list[str],
) -> None:
    """Test the client can ask for how many entities it wants."""
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    with (
        patch(
            "homeassistant.components.usage_prediction.common_control.async_predict_common_control",
            return_value=EntityUsagePredictions(morning=MORNING_ENTITIES),
        ),
        freeze_time(NOW),
    ):
        await client.send_json(
            {"id": 1, "type": "usage_prediction/common_control"} | extra_msg
        )
        msg = await client.receive_json()

    assert msg["success"] is True
    assert msg["result"] == {"entities": expected_entities}
