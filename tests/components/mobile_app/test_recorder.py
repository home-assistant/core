"""The tests for mobile_app recorder."""
from __future__ import annotations

from http import HTTPStatus
from typing import Any

from aiohttp.test_utils import TestClient

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.components.recorder.common import async_wait_recording_done


async def test_exclude_attributes(
    recorder_mock: Recorder,
    setup_ws: None,
    hass: HomeAssistant,
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
    webhook_client: TestClient,
) -> None:
    """Test binary_sensor has event_id and event_score excluded from recording."""
    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"
    now = dt_util.utcnow()

    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "Battery State",
                "state": None,
                "type": "sensor",
                "unique_id": "battery_state",
            },
        },
    )

    assert reg_resp.status == HTTPStatus.CREATED

    update_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "update_sensor_states",
            "data": [
                {
                    "icon": "mdi:battery-unknown",
                    "state": 123,
                    "type": "sensor",
                    "unique_id": "battery_state",
                },
            ],
        },
    )

    assert update_resp.status == HTTPStatus.OK

    json = await update_resp.json()
    assert json["battery_state"]["success"] is True
    assert "is_disabled" not in json["battery_state"]

    update_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "update_sensor_states",
            "data": [
                {
                    "icon": "mdi:battery-unknown",
                    "state": 456,
                    "type": "sensor",
                    "unique_id": "battery_state",
                    "attributes": {
                        "keep": "me",
                        "Available": "not me",
                    },
                },
            ],
        },
    )

    assert update_resp.status == HTTPStatus.OK

    json = await update_resp.json()
    assert json["battery_state"]["success"] is True

    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_1_battery_state")
    assert state
    assert state.state == "456"
    assert state.attributes["Available"] == "not me"
    assert state.attributes["keep"] == "me"
    await async_wait_recording_done(hass)

    states = await hass.async_add_executor_job(
        get_significant_states, hass, now, None, hass.states.async_entity_ids()
    )
    assert len(states) >= 1
    state = states["sensor.test_1_battery_state"][-1]
    assert "Available" not in state.attributes
    assert "keep" in state.attributes
    assert ATTR_FRIENDLY_NAME in state.attributes
