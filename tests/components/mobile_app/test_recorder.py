"""The tests for unifiprotect recorder."""
from __future__ import annotations

from http import HTTPStatus

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.components.recorder.common import async_wait_recording_done


async def test_exclude_attributes(
    recorder_mock: Recorder, hass: HomeAssistant, create_registrations, webhook_client
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

    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_1_battery_state")
    assert state
    assert state.state == "123"
    await async_wait_recording_done(hass)

    states = await hass.async_add_executor_job(
        get_significant_states, hass, now, None, hass.states.async_entity_ids()
    )
    assert len(states) >= 1
    for entity_states in states.values():
        for state in entity_states:
            assert "Available" not in state.attributes
            assert ATTR_FRIENDLY_NAME in state.attributes
