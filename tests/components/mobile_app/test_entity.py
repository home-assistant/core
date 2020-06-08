"""Entity tests for mobile_app."""

import logging

from homeassistant.const import STATE_UNKNOWN, UNIT_PERCENTAGE
from homeassistant.helpers import device_registry

_LOGGER = logging.getLogger(__name__)


async def test_sensor(hass, create_registrations, webhook_client):
    """Test that sensors can be registered and updated."""
    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"

    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "attributes": {"foo": "bar"},
                "device_class": "battery",
                "icon": "mdi:battery",
                "name": "Battery State",
                "state": 100,
                "type": "sensor",
                "unique_id": "battery_state",
                "unit_of_measurement": UNIT_PERCENTAGE,
            },
        },
    )

    assert reg_resp.status == 201

    json = await reg_resp.json()
    assert json == {"success": True}
    await hass.async_block_till_done()

    entity = hass.states.get("sensor.test_1_battery_state")
    assert entity is not None

    assert entity.attributes["device_class"] == "battery"
    assert entity.attributes["icon"] == "mdi:battery"
    assert entity.attributes["unit_of_measurement"] == UNIT_PERCENTAGE
    assert entity.attributes["foo"] == "bar"
    assert entity.domain == "sensor"
    assert entity.name == "Test 1 Battery State"
    assert entity.state == "100"

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
                # This invalid data should not invalidate whole request
                {"type": "sensor", "unique_id": "invalid_state", "invalid": "data"},
            ],
        },
    )

    assert update_resp.status == 200

    json = await update_resp.json()
    assert json["invalid_state"]["success"] is False

    updated_entity = hass.states.get("sensor.test_1_battery_state")
    assert updated_entity.state == "123"

    dev_reg = await device_registry.async_get_registry(hass)
    assert len(dev_reg.devices) == len(create_registrations)


async def test_sensor_must_register(hass, create_registrations, webhook_client):
    """Test that sensors must be registered before updating."""
    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"
    resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "update_sensor_states",
            "data": [{"state": 123, "type": "sensor", "unique_id": "battery_state"}],
        },
    )

    assert resp.status == 200

    json = await resp.json()
    assert json["battery_state"]["success"] is False
    assert json["battery_state"]["error"]["code"] == "not_registered"


async def test_sensor_id_no_dupes(hass, create_registrations, webhook_client):
    """Test that sensors must have a unique ID."""
    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"

    payload = {
        "type": "register_sensor",
        "data": {
            "attributes": {"foo": "bar"},
            "device_class": "battery",
            "icon": "mdi:battery",
            "name": "Battery State",
            "state": 100,
            "type": "sensor",
            "unique_id": "battery_state",
            "unit_of_measurement": UNIT_PERCENTAGE,
        },
    }

    reg_resp = await webhook_client.post(webhook_url, json=payload)

    assert reg_resp.status == 201

    reg_json = await reg_resp.json()
    assert reg_json == {"success": True}

    dupe_resp = await webhook_client.post(webhook_url, json=payload)

    assert dupe_resp.status == 409

    dupe_json = await dupe_resp.json()
    assert dupe_json["success"] is False
    assert dupe_json["error"]["code"] == "duplicate_unique_id"


async def test_register_sensor_no_state(hass, create_registrations, webhook_client):
    """Test that sensors can be registered, when there is no (unknown) state."""
    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"

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

    assert reg_resp.status == 201

    json = await reg_resp.json()
    assert json == {"success": True}
    await hass.async_block_till_done()

    entity = hass.states.get("sensor.test_1_battery_state")
    assert entity is not None

    assert entity.domain == "sensor"
    assert entity.name == "Test 1 Battery State"
    assert entity.state == STATE_UNKNOWN


async def test_update_sensor_no_state(hass, create_registrations, webhook_client):
    """Test that sensors can be updated, when there is no (unknown) state."""
    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"

    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "Battery State",
                "state": 100,
                "type": "sensor",
                "unique_id": "battery_state",
            },
        },
    )

    assert reg_resp.status == 201

    json = await reg_resp.json()
    assert json == {"success": True}
    await hass.async_block_till_done()

    entity = hass.states.get("sensor.test_1_battery_state")
    assert entity is not None
    assert entity.state == "100"

    update_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "update_sensor_states",
            "data": [{"state": None, "type": "sensor", "unique_id": "battery_state"}],
        },
    )

    assert update_resp.status == 200

    json = await update_resp.json()
    assert json == {"battery_state": {"success": True}}

    updated_entity = hass.states.get("sensor.test_1_battery_state")
    assert updated_entity.state == STATE_UNKNOWN
