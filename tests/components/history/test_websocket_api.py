"""The tests the History component websocket_api."""
# pylint: disable=protected-access,invalid-name
from datetime import timedelta
from unittest.mock import patch

import async_timeout
from freezegun import freeze_time
import pytest

from homeassistant.components import history
from homeassistant.components.history import websocket_api
from homeassistant.components.recorder import Recorder
from homeassistant.const import EVENT_HOMEASSISTANT_FINAL_WRITE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.recorder.common import (
    async_recorder_block_till_done,
    async_wait_recording_done,
)
from tests.typing import WebSocketGenerator


def listeners_without_writes(listeners: dict[str, int]) -> dict[str, int]:
    """Return listeners without final write listeners since we are not testing for these."""
    return {
        key: value
        for key, value in listeners.items()
        if key != EVENT_HOMEASSISTANT_FINAL_WRITE
    }


@pytest.mark.usefixtures("hass_history")
def test_setup() -> None:
    """Test setup method of history."""
    # Verification occurs in the fixture


async def test_history_during_period(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test history_during_period."""
    now = dt_util.utcnow()

    await async_setup_component(hass, "history", {})
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
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


async def test_history_during_period_impossible_conditions(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test history_during_period returns when condition cannot be true."""
    await async_setup_component(hass, "history", {})
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
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

    after = dt_util.utcnow()

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "history/history_during_period",
            "start_time": after.isoformat(),
            "end_time": after.isoformat(),
            "entity_ids": ["sensor.test"],
            "include_start_time_state": False,
            "significant_changes_only": False,
            "no_attributes": True,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 1
    assert response["result"] == {}

    future = dt_util.utcnow() + timedelta(hours=10)

    await client.send_json(
        {
            "id": 2,
            "type": "history/history_during_period",
            "start_time": future.isoformat(),
            "entity_ids": ["sensor.test"],
            "include_start_time_state": True,
            "significant_changes_only": True,
            "no_attributes": True,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 2
    assert response["result"] == {}


@pytest.mark.parametrize(
    "time_zone", ["UTC", "Europe/Berlin", "America/Chicago", "US/Hawaii"]
)
async def test_history_during_period_significant_domain(
    time_zone,
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test history_during_period with climate domain."""
    hass.config.set_time_zone(time_zone)
    now = dt_util.utcnow()

    await async_setup_component(hass, "history", {})
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("climate.test", "on", attributes={"temperature": "1"})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("climate.test", "off", attributes={"temperature": "2"})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("climate.test", "off", attributes={"temperature": "3"})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("climate.test", "off", attributes={"temperature": "4"})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("climate.test", "on", attributes={"temperature": "5"})
    await async_wait_recording_done(hass)

    await async_wait_recording_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "history/history_during_period",
            "start_time": now.isoformat(),
            "end_time": now.isoformat(),
            "entity_ids": ["climate.test"],
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
            "entity_ids": ["climate.test"],
            "include_start_time_state": True,
            "significant_changes_only": False,
            "no_attributes": True,
            "minimal_response": True,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 2

    sensor_test_history = response["result"]["climate.test"]
    assert len(sensor_test_history) == 5

    assert sensor_test_history[0]["s"] == "on"
    assert sensor_test_history[0]["a"] == {}
    assert isinstance(sensor_test_history[0]["lu"], float)
    assert "lc" not in sensor_test_history[0]  # skipped if the same a last_updated (lu)

    assert "a" in sensor_test_history[1]
    assert sensor_test_history[1]["s"] == "off"
    assert "lc" not in sensor_test_history[1]  # skipped if the same a last_updated (lu)

    assert sensor_test_history[4]["s"] == "on"
    assert sensor_test_history[4]["a"] == {}

    await client.send_json(
        {
            "id": 3,
            "type": "history/history_during_period",
            "start_time": now.isoformat(),
            "entity_ids": ["climate.test"],
            "include_start_time_state": True,
            "significant_changes_only": False,
            "no_attributes": False,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 3
    sensor_test_history = response["result"]["climate.test"]

    assert len(sensor_test_history) == 5

    assert sensor_test_history[0]["s"] == "on"
    assert sensor_test_history[0]["a"] == {"temperature": "1"}
    assert isinstance(sensor_test_history[0]["lu"], float)
    assert "lc" not in sensor_test_history[0]  # skipped if the same a last_updated (lu)

    assert sensor_test_history[1]["s"] == "off"
    assert isinstance(sensor_test_history[1]["lu"], float)
    assert "lc" not in sensor_test_history[1]  # skipped if the same a last_updated (lu)
    assert sensor_test_history[1]["a"] == {"temperature": "2"}

    assert sensor_test_history[4]["s"] == "on"
    assert sensor_test_history[4]["a"] == {"temperature": "5"}

    await client.send_json(
        {
            "id": 4,
            "type": "history/history_during_period",
            "start_time": now.isoformat(),
            "entity_ids": ["climate.test"],
            "include_start_time_state": True,
            "significant_changes_only": True,
            "no_attributes": False,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 4
    sensor_test_history = response["result"]["climate.test"]

    assert len(sensor_test_history) == 5

    assert sensor_test_history[0]["s"] == "on"
    assert sensor_test_history[0]["a"] == {"temperature": "1"}
    assert isinstance(sensor_test_history[0]["lu"], float)
    assert "lc" not in sensor_test_history[0]  # skipped if the same a last_updated (lu)

    assert sensor_test_history[1]["s"] == "off"
    assert isinstance(sensor_test_history[1]["lu"], float)
    assert "lc" not in sensor_test_history[1]  # skipped if the same a last_updated (lu)
    assert sensor_test_history[1]["a"] == {"temperature": "2"}

    assert sensor_test_history[2]["s"] == "off"
    assert sensor_test_history[2]["a"] == {"temperature": "3"}

    assert sensor_test_history[3]["s"] == "off"
    assert sensor_test_history[3]["a"] == {"temperature": "4"}

    assert sensor_test_history[4]["s"] == "on"
    assert sensor_test_history[4]["a"] == {"temperature": "5"}

    # Test we impute the state time state
    later = dt_util.utcnow()
    await client.send_json(
        {
            "id": 5,
            "type": "history/history_during_period",
            "start_time": later.isoformat(),
            "entity_ids": ["climate.test"],
            "include_start_time_state": True,
            "significant_changes_only": True,
            "no_attributes": False,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 5
    sensor_test_history = response["result"]["climate.test"]

    assert len(sensor_test_history) == 1

    assert sensor_test_history[0]["s"] == "on"
    assert sensor_test_history[0]["a"] == {"temperature": "5"}
    assert sensor_test_history[0]["lu"] == later.timestamp()
    assert "lc" not in sensor_test_history[0]  # skipped if the same a last_updated (lu)


async def test_history_during_period_bad_start_time(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test history_during_period bad state time."""
    await async_setup_component(
        hass,
        "history",
        {"history": {}},
    )

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "history/history_during_period",
            "entity_ids": ["sensor.pet"],
            "start_time": "cats",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_start_time"


async def test_history_during_period_bad_end_time(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test history_during_period bad end time."""
    now = dt_util.utcnow()

    await async_setup_component(
        hass,
        "history",
        {"history": {}},
    )

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "history/history_during_period",
            "entity_ids": ["sensor.pet"],
            "start_time": now.isoformat(),
            "end_time": "dogs",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_end_time"


async def test_history_stream_historical_only(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test history stream."""
    now = dt_util.utcnow()
    await async_setup_component(
        hass,
        "history",
        {},
    )
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.one", "on", attributes={"any": "attr"})
    sensor_one_last_updated = hass.states.get("sensor.one").last_updated
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.two", "off", attributes={"any": "attr"})
    sensor_two_last_updated = hass.states.get("sensor.two").last_updated
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.three", "off", attributes={"any": "changed"})
    sensor_three_last_updated = hass.states.get("sensor.three").last_updated
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.four", "off", attributes={"any": "again"})
    sensor_four_last_updated = hass.states.get("sensor.four").last_updated
    await async_recorder_block_till_done(hass)
    hass.states.async_set("switch.excluded", "off", attributes={"any": "again"})
    await async_wait_recording_done(hass)

    await async_wait_recording_done(hass)
    end_time = dt_util.utcnow()

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "history/stream",
            "entity_ids": ["sensor.one", "sensor.two", "sensor.three", "sensor.four"],
            "start_time": now.isoformat(),
            "end_time": end_time.isoformat(),
            "include_start_time_state": True,
            "significant_changes_only": False,
            "no_attributes": True,
            "minimal_response": True,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 1
    assert response["type"] == "result"

    response = await client.receive_json()

    assert response == {
        "event": {
            "end_time": sensor_four_last_updated.timestamp(),
            "start_time": now.timestamp(),
            "states": {
                "sensor.four": [
                    {"a": {}, "lu": sensor_four_last_updated.timestamp(), "s": "off"}
                ],
                "sensor.one": [
                    {"a": {}, "lu": sensor_one_last_updated.timestamp(), "s": "on"}
                ],
                "sensor.three": [
                    {"a": {}, "lu": sensor_three_last_updated.timestamp(), "s": "off"}
                ],
                "sensor.two": [
                    {"a": {}, "lu": sensor_two_last_updated.timestamp(), "s": "off"}
                ],
            },
        },
        "id": 1,
        "type": "event",
    }


async def test_history_stream_significant_domain_historical_only(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the stream with climate domain with historical states only."""
    now = dt_util.utcnow()

    await async_setup_component(hass, "history", {})
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("climate.test", "on", attributes={"temperature": "1"})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("climate.test", "off", attributes={"temperature": "2"})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("climate.test", "off", attributes={"temperature": "3"})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("climate.test", "off", attributes={"temperature": "4"})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("climate.test", "on", attributes={"temperature": "5"})
    await async_wait_recording_done(hass)

    await async_wait_recording_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "history/stream",
            "start_time": now.isoformat(),
            "end_time": now.isoformat(),
            "entity_ids": ["climate.test"],
            "include_start_time_state": True,
            "significant_changes_only": False,
            "no_attributes": True,
        }
    )
    async with async_timeout.timeout(3):
        response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 1
    assert response["type"] == "result"
    async with async_timeout.timeout(3):
        response = await client.receive_json()
    assert response == {
        "event": {
            "end_time": now.timestamp(),
            "start_time": now.timestamp(),
            "states": {},
        },
        "id": 1,
        "type": "event",
    }

    end_time = dt_util.utcnow()
    await client.send_json(
        {
            "id": 2,
            "type": "history/stream",
            "start_time": now.isoformat(),
            "end_time": end_time.isoformat(),
            "entity_ids": ["climate.test"],
            "include_start_time_state": True,
            "significant_changes_only": False,
            "no_attributes": True,
            "minimal_response": True,
        }
    )
    async with async_timeout.timeout(3):
        response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 2
    assert response["type"] == "result"

    async with async_timeout.timeout(3):
        response = await client.receive_json()
    sensor_test_history = response["event"]["states"]["climate.test"]
    assert len(sensor_test_history) == 5

    assert sensor_test_history[0]["s"] == "on"
    assert sensor_test_history[0]["a"] == {}
    assert isinstance(sensor_test_history[0]["lu"], float)
    assert "lc" not in sensor_test_history[0]  # skipped if the same a last_updated (lu)

    assert "a" in sensor_test_history[1]
    assert sensor_test_history[1]["s"] == "off"
    assert "lc" not in sensor_test_history[1]  # skipped if the same a last_updated (lu)

    assert sensor_test_history[4]["s"] == "on"
    assert sensor_test_history[4]["a"] == {}

    await client.send_json(
        {
            "id": 3,
            "type": "history/stream",
            "start_time": now.isoformat(),
            "end_time": end_time.isoformat(),
            "entity_ids": ["climate.test"],
            "include_start_time_state": True,
            "significant_changes_only": False,
            "no_attributes": False,
        }
    )
    async with async_timeout.timeout(3):
        response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 3
    assert response["type"] == "result"

    async with async_timeout.timeout(3):
        response = await client.receive_json()
    sensor_test_history = response["event"]["states"]["climate.test"]

    assert len(sensor_test_history) == 5

    assert sensor_test_history[0]["s"] == "on"
    assert sensor_test_history[0]["a"] == {"temperature": "1"}
    assert isinstance(sensor_test_history[0]["lu"], float)
    assert "lc" not in sensor_test_history[0]  # skipped if the same a last_updated (lu)

    assert sensor_test_history[1]["s"] == "off"
    assert isinstance(sensor_test_history[1]["lu"], float)
    assert "lc" not in sensor_test_history[1]  # skipped if the same a last_updated (lu)
    assert sensor_test_history[1]["a"] == {"temperature": "2"}

    assert sensor_test_history[4]["s"] == "on"
    assert sensor_test_history[4]["a"] == {"temperature": "5"}

    await client.send_json(
        {
            "id": 4,
            "type": "history/stream",
            "start_time": now.isoformat(),
            "end_time": end_time.isoformat(),
            "entity_ids": ["climate.test"],
            "include_start_time_state": True,
            "significant_changes_only": True,
            "no_attributes": False,
        }
    )
    async with async_timeout.timeout(3):
        response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 4
    assert response["type"] == "result"

    async with async_timeout.timeout(3):
        response = await client.receive_json()
    sensor_test_history = response["event"]["states"]["climate.test"]

    assert len(sensor_test_history) == 5

    assert sensor_test_history[0]["s"] == "on"
    assert sensor_test_history[0]["a"] == {"temperature": "1"}
    assert isinstance(sensor_test_history[0]["lu"], float)
    assert "lc" not in sensor_test_history[0]  # skipped if the same a last_updated (lu)

    assert sensor_test_history[1]["s"] == "off"
    assert isinstance(sensor_test_history[1]["lu"], float)
    assert "lc" not in sensor_test_history[1]  # skipped if the same a last_updated (lu)
    assert sensor_test_history[1]["a"] == {"temperature": "2"}

    assert sensor_test_history[2]["s"] == "off"
    assert sensor_test_history[2]["a"] == {"temperature": "3"}

    assert sensor_test_history[3]["s"] == "off"
    assert sensor_test_history[3]["a"] == {"temperature": "4"}

    assert sensor_test_history[4]["s"] == "on"
    assert sensor_test_history[4]["a"] == {"temperature": "5"}

    # Test we impute the state time state
    later = dt_util.utcnow()
    await client.send_json(
        {
            "id": 5,
            "type": "history/stream",
            "start_time": later.isoformat(),
            "end_time": later.isoformat(),
            "entity_ids": ["climate.test"],
            "include_start_time_state": True,
            "significant_changes_only": True,
            "no_attributes": False,
        }
    )
    async with async_timeout.timeout(3):
        response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 5
    assert response["type"] == "result"

    async with async_timeout.timeout(3):
        response = await client.receive_json()
    sensor_test_history = response["event"]["states"]["climate.test"]

    assert len(sensor_test_history) == 1

    assert sensor_test_history[0]["s"] == "on"
    assert sensor_test_history[0]["a"] == {"temperature": "5"}
    assert sensor_test_history[0]["lu"] == later.timestamp()
    assert "lc" not in sensor_test_history[0]  # skipped if the same a last_updated (lu)


async def test_history_stream_bad_start_time(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test history stream bad state time."""
    await async_setup_component(
        hass,
        "history",
        {"history": {}},
    )

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "history/stream",
            "entity_ids": ["climate.test"],
            "start_time": "cats",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_start_time"


async def test_history_stream_end_time_before_start_time(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test history stream with an end_time before the start_time."""
    end_time = dt_util.utcnow() - timedelta(seconds=2)
    start_time = dt_util.utcnow() - timedelta(seconds=1)

    await async_setup_component(
        hass,
        "history",
        {"history": {}},
    )

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "history/stream",
            "entity_ids": ["climate.test"],
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_end_time"


async def test_history_stream_bad_end_time(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test history stream bad end time."""
    now = dt_util.utcnow()

    await async_setup_component(
        hass,
        "history",
        {"history": {}},
    )

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "history/stream",
            "entity_ids": ["climate.test"],
            "start_time": now.isoformat(),
            "end_time": "dogs",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_end_time"


async def test_history_stream_live_no_attributes_minimal_response(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test history stream with history and live data and no_attributes and minimal_response."""
    now = dt_util.utcnow()
    await async_setup_component(
        hass,
        "history",
        {},
    )
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.one", "on", attributes={"any": "attr"})
    sensor_one_last_updated = hass.states.get("sensor.one").last_updated
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.two", "off", attributes={"any": "attr"})
    sensor_two_last_updated = hass.states.get("sensor.two").last_updated
    await async_recorder_block_till_done(hass)
    hass.states.async_set("switch.excluded", "off", attributes={"any": "again"})
    await async_wait_recording_done(hass)

    await async_wait_recording_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "history/stream",
            "entity_ids": ["sensor.one", "sensor.two"],
            "start_time": now.isoformat(),
            "include_start_time_state": True,
            "significant_changes_only": False,
            "no_attributes": True,
            "minimal_response": True,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 1
    assert response["type"] == "result"

    response = await client.receive_json()
    first_end_time = sensor_two_last_updated.timestamp()

    assert response == {
        "event": {
            "end_time": first_end_time,
            "start_time": now.timestamp(),
            "states": {
                "sensor.one": [
                    {"a": {}, "lu": sensor_one_last_updated.timestamp(), "s": "on"}
                ],
                "sensor.two": [
                    {"a": {}, "lu": sensor_two_last_updated.timestamp(), "s": "off"}
                ],
            },
        },
        "id": 1,
        "type": "event",
    }

    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.one", "one", attributes={"any": "attr"})
    hass.states.async_set("sensor.two", "two", attributes={"any": "attr"})
    await async_recorder_block_till_done(hass)

    sensor_one_last_updated = hass.states.get("sensor.one").last_updated
    sensor_two_last_updated = hass.states.get("sensor.two").last_updated
    response = await client.receive_json()
    assert response == {
        "event": {
            "states": {
                "sensor.one": [{"lu": sensor_one_last_updated.timestamp(), "s": "one"}],
                "sensor.two": [{"lu": sensor_two_last_updated.timestamp(), "s": "two"}],
            },
        },
        "id": 1,
        "type": "event",
    }


async def test_history_stream_live(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test history stream with history and live data."""
    now = dt_util.utcnow()
    await async_setup_component(
        hass,
        "history",
        {},
    )
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.one", "on", attributes={"any": "attr"})
    sensor_one_last_updated = hass.states.get("sensor.one").last_updated
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.two", "off", attributes={"any": "attr"})
    sensor_two_last_updated = hass.states.get("sensor.two").last_updated
    await async_recorder_block_till_done(hass)
    hass.states.async_set("switch.excluded", "off", attributes={"any": "again"})
    await async_wait_recording_done(hass)

    await async_wait_recording_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "history/stream",
            "entity_ids": ["sensor.one", "sensor.two"],
            "start_time": now.isoformat(),
            "include_start_time_state": True,
            "significant_changes_only": False,
            "no_attributes": False,
            "minimal_response": False,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 1
    assert response["type"] == "result"

    response = await client.receive_json()
    first_end_time = sensor_two_last_updated.timestamp()

    assert response == {
        "event": {
            "end_time": first_end_time,
            "start_time": now.timestamp(),
            "states": {
                "sensor.one": [
                    {
                        "a": {"any": "attr"},
                        "lu": sensor_one_last_updated.timestamp(),
                        "s": "on",
                    }
                ],
                "sensor.two": [
                    {
                        "a": {"any": "attr"},
                        "lu": sensor_two_last_updated.timestamp(),
                        "s": "off",
                    }
                ],
            },
        },
        "id": 1,
        "type": "event",
    }

    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.one", "on", attributes={"diff": "attr"})
    hass.states.async_set("sensor.two", "two", attributes={"any": "attr"})
    await async_recorder_block_till_done(hass)

    sensor_one_last_updated = hass.states.get("sensor.one").last_updated
    sensor_one_last_changed = hass.states.get("sensor.one").last_changed
    sensor_two_last_updated = hass.states.get("sensor.two").last_updated
    response = await client.receive_json()
    assert response == {
        "event": {
            "states": {
                "sensor.one": [
                    {
                        "lc": sensor_one_last_changed.timestamp(),
                        "lu": sensor_one_last_updated.timestamp(),
                        "s": "on",
                        "a": {"diff": "attr"},
                    }
                ],
                "sensor.two": [
                    {
                        "lu": sensor_two_last_updated.timestamp(),
                        "s": "two",
                        "a": {"any": "attr"},
                    }
                ],
            },
        },
        "id": 1,
        "type": "event",
    }


async def test_history_stream_live_minimal_response(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test history stream with history and live data and minimal_response."""
    now = dt_util.utcnow()
    await async_setup_component(
        hass,
        "history",
        {},
    )
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.one", "on", attributes={"any": "attr"})
    sensor_one_last_updated = hass.states.get("sensor.one").last_updated
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.two", "off", attributes={"any": "attr"})
    sensor_two_last_updated = hass.states.get("sensor.two").last_updated
    await async_recorder_block_till_done(hass)
    hass.states.async_set("switch.excluded", "off", attributes={"any": "again"})
    await async_wait_recording_done(hass)

    await async_wait_recording_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "history/stream",
            "entity_ids": ["sensor.one", "sensor.two"],
            "start_time": now.isoformat(),
            "include_start_time_state": True,
            "significant_changes_only": False,
            "no_attributes": False,
            "minimal_response": True,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 1
    assert response["type"] == "result"

    response = await client.receive_json()
    first_end_time = sensor_two_last_updated.timestamp()

    assert response == {
        "event": {
            "end_time": first_end_time,
            "start_time": now.timestamp(),
            "states": {
                "sensor.one": [
                    {
                        "a": {"any": "attr"},
                        "lu": sensor_one_last_updated.timestamp(),
                        "s": "on",
                    }
                ],
                "sensor.two": [
                    {
                        "a": {"any": "attr"},
                        "lu": sensor_two_last_updated.timestamp(),
                        "s": "off",
                    }
                ],
            },
        },
        "id": 1,
        "type": "event",
    }

    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.one", "on", attributes={"diff": "attr"})
    hass.states.async_set("sensor.two", "two", attributes={"any": "attr"})
    # Only sensor.two has changed
    sensor_one_last_updated = hass.states.get("sensor.one").last_updated
    sensor_two_last_updated = hass.states.get("sensor.two").last_updated
    hass.states.async_remove("sensor.one")
    hass.states.async_remove("sensor.two")
    await async_recorder_block_till_done(hass)

    response = await client.receive_json()
    assert response == {
        "event": {
            "states": {
                "sensor.two": [
                    {
                        "lu": sensor_two_last_updated.timestamp(),
                        "s": "two",
                        "a": {"any": "attr"},
                    }
                ],
            },
        },
        "id": 1,
        "type": "event",
    }


async def test_history_stream_live_no_attributes(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test history stream with history and live data and no_attributes."""
    now = dt_util.utcnow()
    await async_setup_component(
        hass,
        "history",
        {},
    )
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.one", "on", attributes={"any": "attr"})
    sensor_one_last_updated = hass.states.get("sensor.one").last_updated
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.two", "off", attributes={"any": "attr"})
    sensor_two_last_updated = hass.states.get("sensor.two").last_updated
    await async_recorder_block_till_done(hass)
    hass.states.async_set("switch.excluded", "off", attributes={"any": "again"})
    await async_wait_recording_done(hass)

    await async_wait_recording_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "history/stream",
            "start_time": now.isoformat(),
            "entity_ids": ["sensor.one", "sensor.two"],
            "include_start_time_state": True,
            "significant_changes_only": False,
            "no_attributes": True,
            "minimal_response": False,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 1
    assert response["type"] == "result"

    response = await client.receive_json()
    first_end_time = sensor_two_last_updated.timestamp()

    assert response == {
        "event": {
            "end_time": first_end_time,
            "start_time": now.timestamp(),
            "states": {
                "sensor.one": [
                    {"a": {}, "lu": sensor_one_last_updated.timestamp(), "s": "on"}
                ],
                "sensor.two": [
                    {"a": {}, "lu": sensor_two_last_updated.timestamp(), "s": "off"}
                ],
            },
        },
        "id": 1,
        "type": "event",
    }

    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.one", "one", attributes={"diff": "attr"})
    hass.states.async_set("sensor.two", "two", attributes={"diff": "attr"})
    await async_recorder_block_till_done(hass)

    sensor_one_last_updated = hass.states.get("sensor.one").last_updated
    sensor_two_last_updated = hass.states.get("sensor.two").last_updated
    response = await client.receive_json()
    assert response == {
        "event": {
            "states": {
                "sensor.one": [{"lu": sensor_one_last_updated.timestamp(), "s": "one"}],
                "sensor.two": [{"lu": sensor_two_last_updated.timestamp(), "s": "two"}],
            },
        },
        "id": 1,
        "type": "event",
    }


async def test_history_stream_live_no_attributes_minimal_response_specific_entities(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test history stream with history and live data and no_attributes and minimal_response with specific entities."""
    now = dt_util.utcnow()
    wanted_entities = ["sensor.two", "sensor.four", "sensor.one"]
    await async_setup_component(
        hass,
        "history",
        {history.DOMAIN: {}},
    )
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.one", "on", attributes={"any": "attr"})
    sensor_one_last_updated = hass.states.get("sensor.one").last_updated
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.two", "off", attributes={"any": "attr"})
    sensor_two_last_updated = hass.states.get("sensor.two").last_updated
    await async_recorder_block_till_done(hass)
    hass.states.async_set("switch.excluded", "off", attributes={"any": "again"})
    await async_wait_recording_done(hass)

    await async_wait_recording_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "history/stream",
            "entity_ids": wanted_entities,
            "start_time": now.isoformat(),
            "include_start_time_state": True,
            "significant_changes_only": False,
            "no_attributes": True,
            "minimal_response": True,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 1
    assert response["type"] == "result"

    response = await client.receive_json()
    first_end_time = sensor_two_last_updated.timestamp()

    assert response == {
        "event": {
            "end_time": first_end_time,
            "start_time": now.timestamp(),
            "states": {
                "sensor.one": [
                    {"a": {}, "lu": sensor_one_last_updated.timestamp(), "s": "on"}
                ],
                "sensor.two": [
                    {"a": {}, "lu": sensor_two_last_updated.timestamp(), "s": "off"}
                ],
            },
        },
        "id": 1,
        "type": "event",
    }

    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.one", "one", attributes={"any": "attr"})
    hass.states.async_set("sensor.two", "two", attributes={"any": "attr"})
    await async_recorder_block_till_done(hass)

    sensor_one_last_updated = hass.states.get("sensor.one").last_updated
    sensor_two_last_updated = hass.states.get("sensor.two").last_updated
    response = await client.receive_json()
    assert response == {
        "event": {
            "states": {
                "sensor.one": [{"lu": sensor_one_last_updated.timestamp(), "s": "one"}],
                "sensor.two": [{"lu": sensor_two_last_updated.timestamp(), "s": "two"}],
            },
        },
        "id": 1,
        "type": "event",
    }


async def test_history_stream_live_with_future_end_time(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test history stream with history and live data with future end time."""
    now = dt_util.utcnow()
    wanted_entities = ["sensor.two", "sensor.four", "sensor.one"]
    await async_setup_component(
        hass,
        "history",
        {history.DOMAIN: {}},
    )
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.one", "on", attributes={"any": "attr"})
    sensor_one_last_updated = hass.states.get("sensor.one").last_updated
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.two", "off", attributes={"any": "attr"})
    sensor_two_last_updated = hass.states.get("sensor.two").last_updated
    await async_recorder_block_till_done(hass)
    hass.states.async_set("switch.excluded", "off", attributes={"any": "again"})
    await async_wait_recording_done(hass)

    await async_wait_recording_done(hass)

    future = now + timedelta(seconds=10)

    client = await hass_ws_client()
    init_listeners = hass.bus.async_listeners()
    await client.send_json(
        {
            "id": 1,
            "type": "history/stream",
            "entity_ids": wanted_entities,
            "start_time": now.isoformat(),
            "end_time": future.isoformat(),
            "include_start_time_state": True,
            "significant_changes_only": False,
            "no_attributes": True,
            "minimal_response": True,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 1
    assert response["type"] == "result"

    response = await client.receive_json()
    first_end_time = sensor_two_last_updated.timestamp()

    assert response == {
        "event": {
            "end_time": first_end_time,
            "start_time": now.timestamp(),
            "states": {
                "sensor.one": [
                    {"a": {}, "lu": sensor_one_last_updated.timestamp(), "s": "on"}
                ],
                "sensor.two": [
                    {"a": {}, "lu": sensor_two_last_updated.timestamp(), "s": "off"}
                ],
            },
        },
        "id": 1,
        "type": "event",
    }

    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.one", "one", attributes={"any": "attr"})
    hass.states.async_set("sensor.two", "two", attributes={"any": "attr"})
    await async_recorder_block_till_done(hass)

    sensor_one_last_updated = hass.states.get("sensor.one").last_updated
    sensor_two_last_updated = hass.states.get("sensor.two").last_updated
    response = await client.receive_json()
    assert response == {
        "event": {
            "states": {
                "sensor.one": [{"lu": sensor_one_last_updated.timestamp(), "s": "one"}],
                "sensor.two": [{"lu": sensor_two_last_updated.timestamp(), "s": "two"}],
            },
        },
        "id": 1,
        "type": "event",
    }

    async_fire_time_changed(hass, future + timedelta(seconds=1))
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.two", "future", attributes={"any": "attr"})
    # Check our listener got unsubscribed
    await async_wait_recording_done(hass)
    await async_recorder_block_till_done(hass)
    assert listeners_without_writes(
        hass.bus.async_listeners()
    ) == listeners_without_writes(init_listeners)


@pytest.mark.parametrize("include_start_time_state", (True, False))
async def test_history_stream_before_history_starts(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    include_start_time_state,
) -> None:
    """Test history stream before we have history."""
    await async_setup_component(
        hass,
        "history",
        {},
    )
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.one", "on", attributes={"any": "attr"})
    await async_recorder_block_till_done(hass)
    await async_wait_recording_done(hass)
    far_past = dt_util.utcnow() - timedelta(days=1000)
    far_past_end = far_past + timedelta(seconds=10)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "history/stream",
            "entity_ids": ["sensor.one"],
            "start_time": far_past.isoformat(),
            "end_time": far_past_end.isoformat(),
            "include_start_time_state": include_start_time_state,
            "significant_changes_only": False,
            "no_attributes": True,
            "minimal_response": True,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 1
    assert response["type"] == "result"

    response = await client.receive_json()
    assert response == {
        "event": {
            "end_time": far_past_end.timestamp(),
            "start_time": far_past.timestamp(),
            "states": {},
        },
        "id": 1,
        "type": "event",
    }


async def test_history_stream_for_entity_with_no_possible_changes(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test history stream for future with no possible changes where end time is less than or equal to now."""
    await async_setup_component(
        hass,
        "history",
        {},
    )
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.one", "on", attributes={"any": "attr"})
    await async_recorder_block_till_done(hass)
    await async_wait_recording_done(hass)

    last_updated = hass.states.get("sensor.one").last_updated
    start_time = last_updated + timedelta(seconds=10)
    end_time = start_time + timedelta(seconds=10)

    with freeze_time(end_time):
        client = await hass_ws_client()
        await client.send_json(
            {
                "id": 1,
                "type": "history/stream",
                "entity_ids": ["sensor.one"],
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "include_start_time_state": False,
                "significant_changes_only": False,
                "no_attributes": True,
                "minimal_response": True,
            }
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["id"] == 1
        assert response["type"] == "result"

        response = await client.receive_json()
        assert response == {
            "event": {
                "end_time": end_time.timestamp(),
                "start_time": start_time.timestamp(),
                "states": {},
            },
            "id": 1,
            "type": "event",
        }


async def test_overflow_queue(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test overflowing the history stream queue."""
    now = dt_util.utcnow()
    wanted_entities = ["sensor.two", "sensor.four", "sensor.one"]
    with patch.object(websocket_api, "MAX_PENDING_HISTORY_STATES", 5):
        await async_setup_component(
            hass,
            "history",
            {history.DOMAIN: {}},
        )
        await async_setup_component(hass, "sensor", {})
        await async_recorder_block_till_done(hass)
        hass.states.async_set("sensor.one", "on", attributes={"any": "attr"})
        sensor_one_last_updated = hass.states.get("sensor.one").last_updated
        await async_recorder_block_till_done(hass)
        hass.states.async_set("sensor.two", "off", attributes={"any": "attr"})
        sensor_two_last_updated = hass.states.get("sensor.two").last_updated
        await async_recorder_block_till_done(hass)
        hass.states.async_set("switch.excluded", "off", attributes={"any": "again"})
        await async_wait_recording_done(hass)

        await async_wait_recording_done(hass)

        client = await hass_ws_client()
        init_listeners = hass.bus.async_listeners()

        await client.send_json(
            {
                "id": 1,
                "type": "history/stream",
                "entity_ids": wanted_entities,
                "start_time": now.isoformat(),
                "include_start_time_state": True,
                "significant_changes_only": False,
                "no_attributes": True,
                "minimal_response": True,
            }
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["id"] == 1
        assert response["type"] == "result"

        response = await client.receive_json()
        first_end_time = sensor_two_last_updated.timestamp()

        assert response == {
            "event": {
                "end_time": first_end_time,
                "start_time": now.timestamp(),
                "states": {
                    "sensor.one": [
                        {"a": {}, "lu": sensor_one_last_updated.timestamp(), "s": "on"}
                    ],
                    "sensor.two": [
                        {"a": {}, "lu": sensor_two_last_updated.timestamp(), "s": "off"}
                    ],
                },
            },
            "id": 1,
            "type": "event",
        }

        await async_recorder_block_till_done(hass)
        # Overflow the queue
        for val in range(10):
            hass.states.async_set("sensor.one", str(val), attributes={"any": "attr"})
            hass.states.async_set("sensor.two", str(val), attributes={"any": "attr"})
        await async_recorder_block_till_done(hass)

    assert listeners_without_writes(
        hass.bus.async_listeners()
    ) == listeners_without_writes(init_listeners)


async def test_history_during_period_for_invalid_entity_ids(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test history_during_period for valid and invalid entity ids."""
    now = dt_util.utcnow()

    await async_setup_component(hass, "history", {})
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.one", "on", attributes={"any": "attr"})
    sensor_one_last_updated = hass.states.get("sensor.one").last_updated
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.two", "off", attributes={"any": "attr"})
    sensor_two_last_updated = hass.states.get("sensor.two").last_updated
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.three", "off", attributes={"any": "again"})
    await async_recorder_block_till_done(hass)
    await async_wait_recording_done(hass)
    await async_wait_recording_done(hass)

    client = await hass_ws_client()

    await client.send_json(
        {
            "id": 1,
            "type": "history/history_during_period",
            "start_time": now.isoformat(),
            "entity_ids": ["sensor.one"],
            "include_start_time_state": True,
            "significant_changes_only": False,
            "no_attributes": True,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response == {
        "result": {
            "sensor.one": [
                {"a": {}, "lu": sensor_one_last_updated.timestamp(), "s": "on"}
            ],
        },
        "id": 1,
        "type": "result",
        "success": True,
    }

    await client.send_json(
        {
            "id": 2,
            "type": "history/history_during_period",
            "start_time": now.isoformat(),
            "entity_ids": ["sensor.one", "sensor.two"],
            "include_start_time_state": True,
            "significant_changes_only": False,
            "no_attributes": True,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response == {
        "result": {
            "sensor.one": [
                {"a": {}, "lu": sensor_one_last_updated.timestamp(), "s": "on"}
            ],
            "sensor.two": [
                {"a": {}, "lu": sensor_two_last_updated.timestamp(), "s": "off"}
            ],
        },
        "id": 2,
        "type": "result",
        "success": True,
    }

    await client.send_json(
        {
            "id": 3,
            "type": "history/history_during_period",
            "start_time": now.isoformat(),
            "entity_ids": ["sens!or.one", "two"],
            "include_start_time_state": True,
            "significant_changes_only": False,
            "no_attributes": True,
        }
    )
    response = await client.receive_json()
    assert response["success"] is False
    assert response == {
        "error": {
            "code": "invalid_entity_ids",
            "message": "Invalid entity_ids",
        },
        "id": 3,
        "type": "result",
        "success": False,
    }

    await client.send_json(
        {
            "id": 4,
            "type": "history/history_during_period",
            "start_time": now.isoformat(),
            "entity_ids": ["sensor.one", "sensortwo."],
            "include_start_time_state": True,
            "significant_changes_only": False,
            "no_attributes": True,
        }
    )
    response = await client.receive_json()
    assert response["success"] is False
    assert response == {
        "error": {
            "code": "invalid_entity_ids",
            "message": "Invalid entity_ids",
        },
        "id": 4,
        "type": "result",
        "success": False,
    }

    await client.send_json(
        {
            "id": 5,
            "type": "history/history_during_period",
            "start_time": now.isoformat(),
            "entity_ids": ["one", ".sensortwo"],
            "include_start_time_state": True,
            "significant_changes_only": False,
            "no_attributes": True,
        }
    )
    response = await client.receive_json()
    assert response["success"] is False
    assert response == {
        "error": {
            "code": "invalid_entity_ids",
            "message": "Invalid entity_ids",
        },
        "id": 5,
        "type": "result",
        "success": False,
    }


async def test_history_stream_for_invalid_entity_ids(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test history stream for invalid and valid entity ids."""

    now = dt_util.utcnow()
    await async_setup_component(
        hass,
        "history",
        {history.DOMAIN: {}},
    )

    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.one", "on", attributes={"any": "attr"})
    sensor_one_last_updated = hass.states.get("sensor.one").last_updated
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.two", "off", attributes={"any": "attr"})
    sensor_two_last_updated = hass.states.get("sensor.two").last_updated
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.three", "off", attributes={"any": "again"})
    await async_recorder_block_till_done(hass)
    await async_wait_recording_done(hass)

    await async_wait_recording_done(hass)

    client = await hass_ws_client()

    await client.send_json(
        {
            "id": 1,
            "type": "history/stream",
            "start_time": now.isoformat(),
            "entity_ids": ["sensor.one"],
            "include_start_time_state": True,
            "significant_changes_only": False,
            "no_attributes": True,
            "minimal_response": True,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 1
    assert response["type"] == "result"

    response = await client.receive_json()
    assert response == {
        "event": {
            "end_time": sensor_one_last_updated.timestamp(),
            "start_time": now.timestamp(),
            "states": {
                "sensor.one": [
                    {"a": {}, "lu": sensor_one_last_updated.timestamp(), "s": "on"}
                ],
            },
        },
        "id": 1,
        "type": "event",
    }

    await client.send_json(
        {
            "id": 2,
            "type": "history/stream",
            "start_time": now.isoformat(),
            "entity_ids": ["sensor.one", "sensor.two"],
            "include_start_time_state": True,
            "significant_changes_only": False,
            "no_attributes": True,
            "minimal_response": True,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["id"] == 2
    assert response["type"] == "result"

    response = await client.receive_json()
    assert response == {
        "event": {
            "end_time": sensor_two_last_updated.timestamp(),
            "start_time": now.timestamp(),
            "states": {
                "sensor.one": [
                    {"a": {}, "lu": sensor_one_last_updated.timestamp(), "s": "on"}
                ],
                "sensor.two": [
                    {"a": {}, "lu": sensor_two_last_updated.timestamp(), "s": "off"}
                ],
            },
        },
        "id": 2,
        "type": "event",
    }

    await client.send_json(
        {
            "id": 3,
            "type": "history/stream",
            "start_time": now.isoformat(),
            "entity_ids": ["sens!or.one", "two"],
            "include_start_time_state": True,
            "significant_changes_only": False,
            "no_attributes": True,
            "minimal_response": True,
        }
    )
    response = await client.receive_json()
    assert response["success"] is False
    assert response["id"] == 3
    assert response["type"] == "result"
    assert response == {
        "error": {
            "code": "invalid_entity_ids",
            "message": "Invalid entity_ids",
        },
        "id": 3,
        "type": "result",
        "success": False,
    }

    await client.send_json(
        {
            "id": 4,
            "type": "history/stream",
            "start_time": now.isoformat(),
            "entity_ids": ["sensor.one", "sensortwo."],
            "include_start_time_state": True,
            "significant_changes_only": False,
            "no_attributes": True,
            "minimal_response": True,
        }
    )
    response = await client.receive_json()
    assert response["success"] is False
    assert response["id"] == 4
    assert response["type"] == "result"
    assert response == {
        "error": {
            "code": "invalid_entity_ids",
            "message": "Invalid entity_ids",
        },
        "id": 4,
        "type": "result",
        "success": False,
    }

    await client.send_json(
        {
            "id": 5,
            "type": "history/stream",
            "start_time": now.isoformat(),
            "entity_ids": ["one", ".sensortwo"],
            "include_start_time_state": True,
            "significant_changes_only": False,
            "no_attributes": True,
            "minimal_response": True,
        }
    )
    response = await client.receive_json()
    assert response["success"] is False
    assert response["id"] == 5
    assert response["type"] == "result"
    assert response == {
        "error": {
            "code": "invalid_entity_ids",
            "message": "Invalid entity_ids",
        },
        "id": 5,
        "type": "result",
        "success": False,
    }
