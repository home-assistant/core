"""The tests the History component websocket_api."""

import pytest

from homeassistant.components import recorder
from homeassistant.components.recorder import Recorder
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.components.recorder.common import (
    async_recorder_block_till_done,
    async_wait_recording_done,
    old_db_schema,
)
from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
def db_schema_32():
    """Fixture to initialize the db with the old schema 32."""
    with old_db_schema("32"):
        yield


async def test_history_during_period(
    hass: HomeAssistant, recorder_mock: Recorder, hass_ws_client: WebSocketGenerator
) -> None:
    """Test history_during_period."""
    now = dt_util.utcnow()

    await async_setup_component(hass, "history", {})
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    recorder.get_instance(hass).states_meta_manager.active = False
    assert recorder.get_instance(hass).schema_version == 32

    hass.states.async_set("sensor.test", "on", attributes={"any": "attr"})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.test", "off", attributes={"any": "attr"})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.test", "off", attributes={"any": "changed"})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.test", "off", attributes={"any": "again"})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.test", "on", attributes={"any": "attr"})
    await async_wait_recording_done(hass)

    await async_wait_recording_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "history/history_during_period",
            "start_time": now.isoformat(),
            "end_time": now.isoformat(),
            "entity_ids": ["sensor.test"],
            "include_start_time_state": True,
            "significant_changes_only": False,
            "no_attributes": True,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {}

    await client.send_json(
        {
            "id": 2,
            "type": "history/history_during_period",
            "start_time": now.isoformat(),
            "entity_ids": ["sensor.test"],
            "include_start_time_state": True,
            "significant_changes_only": False,
            "no_attributes": True,
            "minimal_response": True,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 2

    sensor_test_history = response["result"]["sensor.test"]
    assert len(sensor_test_history) == 3

    assert sensor_test_history[0]["s"] == "on"
    assert sensor_test_history[0]["a"] == {}
    assert isinstance(sensor_test_history[0]["lu"], float)
    assert "lc" not in sensor_test_history[0]  # skipped if the same a last_updated (lu)

    assert "a" not in sensor_test_history[1]
    assert sensor_test_history[1]["s"] == "off"
    assert isinstance(sensor_test_history[1]["lu"], float)
    assert "lc" not in sensor_test_history[1]  # skipped if the same a last_updated (lu)

    assert sensor_test_history[2]["s"] == "on"
    assert "a" not in sensor_test_history[2]

    await client.send_json(
        {
            "id": 3,
            "type": "history/history_during_period",
            "start_time": now.isoformat(),
            "entity_ids": ["sensor.test"],
            "include_start_time_state": True,
            "significant_changes_only": False,
            "no_attributes": False,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 3
    sensor_test_history = response["result"]["sensor.test"]

    assert len(sensor_test_history) == 5

    assert sensor_test_history[0]["s"] == "on"
    assert sensor_test_history[0]["a"] == {"any": "attr"}
    assert isinstance(sensor_test_history[0]["lu"], float)
    assert "lc" not in sensor_test_history[0]  # skipped if the same a last_updated (lu)

    assert sensor_test_history[1]["s"] == "off"
    assert isinstance(sensor_test_history[1]["lu"], float)
    assert "lc" not in sensor_test_history[1]  # skipped if the same a last_updated (lu)
    assert sensor_test_history[1]["a"] == {"any": "attr"}

    assert sensor_test_history[4]["s"] == "on"
    assert sensor_test_history[4]["a"] == {"any": "attr"}

    await client.send_json(
        {
            "id": 4,
            "type": "history/history_during_period",
            "start_time": now.isoformat(),
            "entity_ids": ["sensor.test"],
            "include_start_time_state": True,
            "significant_changes_only": True,
            "no_attributes": False,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 4
    sensor_test_history = response["result"]["sensor.test"]

    assert len(sensor_test_history) == 3

    assert sensor_test_history[0]["s"] == "on"
    assert sensor_test_history[0]["a"] == {"any": "attr"}
    assert isinstance(sensor_test_history[0]["lu"], float)
    assert "lc" not in sensor_test_history[0]  # skipped if the same a last_updated (lu)

    assert sensor_test_history[1]["s"] == "off"
    assert isinstance(sensor_test_history[1]["lu"], float)
    assert "lc" not in sensor_test_history[1]  # skipped if the same a last_updated (lu)
    assert sensor_test_history[1]["a"] == {"any": "attr"}

    assert sensor_test_history[2]["s"] == "on"
    assert sensor_test_history[2]["a"] == {"any": "attr"}
