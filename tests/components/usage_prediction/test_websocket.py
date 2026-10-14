"""Test usage_prediction WebSocket API."""

from collections.abc import Generator
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import Mock, patch

from freezegun import freeze_time
import pytest

from homeassistant.components.usage_prediction import DOMAIN
from homeassistant.components.usage_prediction.const import DEFAULT_LIMIT
from homeassistant.components.usage_prediction.models import EntityUsagePredictions
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockUser
from tests.typing import WebSocketGenerator

# Morning in the test time zone
NOW = datetime(2026, 8, 26, 15, 0, 0, tzinfo=dt_util.UTC)

MORNING_ENTITIES = [f"light.morning_{index}" for index in range(60)]


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
        pytest.param({}, MORNING_ENTITIES[:DEFAULT_LIMIT], id="default"),
        pytest.param({"limit": 3}, MORNING_ENTITIES[:3], id="fewer"),
        pytest.param({"limit": 100}, MORNING_ENTITIES, id="more_than_predicted"),
    ],
)
async def test_common_control_limit(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_predict_common_control: Mock,
    extra_msg: dict[str, Any],
    expected_entities: list[str],
) -> None:
    """Test the client can ask for how many entities it wants."""
    mock_predict_common_control.return_value = EntityUsagePredictions(
        morning=MORNING_ENTITIES
    )
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    with freeze_time(NOW):
        await client.send_json(
            {"id": 1, "type": "usage_prediction/common_control"} | extra_msg
        )
        msg = await client.receive_json()

    assert msg["success"] is True
    assert msg["result"] == {"entities": expected_entities}


@pytest.mark.usefixtures("recorder_mock")
@pytest.mark.parametrize(
    "limit",
    [
        pytest.param(0, id="below_minimum"),
        pytest.param(-1, id="negative"),
        pytest.param("3", id="string"),
        pytest.param(3.5, id="float"),
    ],
)
async def test_common_control_invalid_limit(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_predict_common_control: Mock,
    limit: float | str,
) -> None:
    """Test an invalid limit is rejected without predicting."""
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    await client.send_json(
        {"id": 1, "type": "usage_prediction/common_control", "limit": limit}
    )
    msg = await client.receive_json()

    assert msg["success"] is False
    assert msg["error"]["code"] == "invalid_format"
    assert mock_predict_common_control.call_count == 0


@pytest.mark.usefixtures("recorder_mock")
async def test_common_control_limit_served_from_cache(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_predict_common_control: Mock,
) -> None:
    """Test a later call with a different limit is served from the cache."""
    mock_predict_common_control.return_value = EntityUsagePredictions(
        morning=MORNING_ENTITIES
    )
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    with freeze_time(NOW):
        await client.send_json(
            {"id": 1, "type": "usage_prediction/common_control", "limit": 3}
        )
        first = await client.receive_json()
        await client.send_json(
            {"id": 2, "type": "usage_prediction/common_control", "limit": 20}
        )
        second = await client.receive_json()

    assert first["result"] == {"entities": MORNING_ENTITIES[:3]}
    assert second["result"] == {"entities": MORNING_ENTITIES[:20]}
    assert mock_predict_common_control.call_count == 1
