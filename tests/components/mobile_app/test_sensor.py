"""Entity tests for mobile_app."""
from http import HTTPStatus

import pytest

from homeassistant.components.sensor import DEVICE_CLASS_DATE, DEVICE_CLASS_TIMESTAMP
from homeassistant.const import PERCENTAGE, STATE_UNKNOWN
from homeassistant.helpers import device_registry as dr, entity_registry as er


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
                "entity_category": "diagnostic",
                "unique_id": "battery_state",
                "state_class": "total",
                "unit_of_measurement": PERCENTAGE,
            },
        },
    )

    assert reg_resp.status == HTTPStatus.CREATED

    json = await reg_resp.json()
    assert json == {"success": True}
    await hass.async_block_till_done()

    entity = hass.states.get("sensor.test_1_battery_state")
    assert entity is not None

    assert entity.attributes["device_class"] == "battery"
    assert entity.attributes["icon"] == "mdi:battery"
    assert entity.attributes["unit_of_measurement"] == PERCENTAGE
    assert entity.attributes["foo"] == "bar"
    assert entity.attributes["state_class"] == "total"
    assert entity.domain == "sensor"
    assert entity.name == "Test 1 Battery State"
    assert entity.state == "100"

    assert (
        er.async_get(hass).async_get("sensor.test_1_battery_state").entity_category
        == "diagnostic"
    )

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

    assert update_resp.status == HTTPStatus.OK

    json = await update_resp.json()
    assert json["invalid_state"]["success"] is False

    updated_entity = hass.states.get("sensor.test_1_battery_state")
    assert updated_entity.state == "123"
    assert "foo" not in updated_entity.attributes

    dev_reg = dr.async_get(hass)
    assert len(dev_reg.devices) == len(create_registrations)

    # Reload to verify state is restored
    config_entry = hass.config_entries.async_entries("mobile_app")[1]
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    unloaded_entity = hass.states.get("sensor.test_1_battery_state")
    assert unloaded_entity.state == "unavailable"

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    restored_entity = hass.states.get("sensor.test_1_battery_state")
    assert restored_entity.state == updated_entity.state
    assert restored_entity.attributes == updated_entity.attributes


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

    assert resp.status == HTTPStatus.OK

    json = await resp.json()
    assert json["battery_state"]["success"] is False
    assert json["battery_state"]["error"]["code"] == "not_registered"


async def test_sensor_id_no_dupes(hass, create_registrations, webhook_client, caplog):
    """Test that a duplicate unique ID in registration updates the sensor."""
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
            "unit_of_measurement": PERCENTAGE,
        },
    }

    reg_resp = await webhook_client.post(webhook_url, json=payload)

    assert reg_resp.status == HTTPStatus.CREATED

    reg_json = await reg_resp.json()
    assert reg_json == {"success": True}
    await hass.async_block_till_done()

    assert "Re-register" not in caplog.text

    entity = hass.states.get("sensor.test_1_battery_state")
    assert entity is not None

    assert entity.attributes["device_class"] == "battery"
    assert entity.attributes["icon"] == "mdi:battery"
    assert entity.attributes["unit_of_measurement"] == PERCENTAGE
    assert entity.attributes["foo"] == "bar"
    assert entity.domain == "sensor"
    assert entity.name == "Test 1 Battery State"
    assert entity.state == "100"

    payload["data"]["state"] = 99
    dupe_resp = await webhook_client.post(webhook_url, json=payload)

    assert dupe_resp.status == HTTPStatus.CREATED
    dupe_reg_json = await dupe_resp.json()
    assert dupe_reg_json == {"success": True}
    await hass.async_block_till_done()

    assert "Re-register" in caplog.text

    entity = hass.states.get("sensor.test_1_battery_state")
    assert entity is not None

    assert entity.attributes["device_class"] == "battery"
    assert entity.attributes["icon"] == "mdi:battery"
    assert entity.attributes["unit_of_measurement"] == PERCENTAGE
    assert entity.attributes["foo"] == "bar"
    assert entity.domain == "sensor"
    assert entity.name == "Test 1 Battery State"
    assert entity.state == "99"


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

    assert reg_resp.status == HTTPStatus.CREATED

    json = await reg_resp.json()
    assert json == {"success": True}
    await hass.async_block_till_done()

    entity = hass.states.get("sensor.test_1_battery_state")
    assert entity is not None

    assert entity.domain == "sensor"
    assert entity.name == "Test 1 Battery State"
    assert entity.state == STATE_UNKNOWN

    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "Backup Battery State",
                "type": "sensor",
                "unique_id": "backup_battery_state",
            },
        },
    )

    assert reg_resp.status == HTTPStatus.CREATED

    json = await reg_resp.json()
    assert json == {"success": True}
    await hass.async_block_till_done()

    entity = hass.states.get("sensor.test_1_backup_battery_state")
    assert entity

    assert entity.domain == "sensor"
    assert entity.name == "Test 1 Backup Battery State"
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

    assert reg_resp.status == HTTPStatus.CREATED

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

    assert update_resp.status == HTTPStatus.OK

    json = await update_resp.json()
    assert json == {"battery_state": {"success": True}}

    updated_entity = hass.states.get("sensor.test_1_battery_state")
    assert updated_entity.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "device_class,native_value,state_value",
    [
        (DEVICE_CLASS_DATE, "2021-11-18", "2021-11-18"),
        (
            DEVICE_CLASS_TIMESTAMP,
            "2021-11-18T20:25:00+00:00",
            "2021-11-18T20:25:00+00:00",
        ),
        (
            DEVICE_CLASS_TIMESTAMP,
            "2021-11-18 20:25:00+01:00",
            "2021-11-18T19:25:00+00:00",
        ),
    ],
)
async def test_sensor_datetime(
    hass, create_registrations, webhook_client, device_class, native_value, state_value
):
    """Test that sensors can be registered and updated."""
    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"

    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "device_class": device_class,
                "name": "Datetime sensor test",
                "state": native_value,
                "type": "sensor",
                "unique_id": "super_unique",
            },
        },
    )

    assert reg_resp.status == HTTPStatus.CREATED

    json = await reg_resp.json()
    assert json == {"success": True}
    await hass.async_block_till_done()

    entity = hass.states.get("sensor.test_1_datetime_sensor_test")
    assert entity is not None

    assert entity.attributes["device_class"] == device_class
    assert entity.domain == "sensor"
    assert entity.state == state_value
