"""Entity tests for mobile_app."""
from http import HTTPStatus

import pytest

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr


async def test_sensor(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    create_registrations,
    webhook_client,
) -> None:
    """Test that sensors can be registered and updated."""
    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"

    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "attributes": {"foo": "bar"},
                "device_class": "plug",
                "icon": "mdi:power-plug",
                "name": "Is Charging",
                "state": True,
                "type": "binary_sensor",
                "unique_id": "is_charging",
            },
        },
    )

    assert reg_resp.status == HTTPStatus.CREATED

    json = await reg_resp.json()
    assert json == {"success": True}
    await hass.async_block_till_done()

    entity = hass.states.get("binary_sensor.test_1_is_charging")
    assert entity is not None

    assert entity.attributes["device_class"] == "plug"
    assert entity.attributes["icon"] == "mdi:power-plug"
    assert entity.attributes["foo"] == "bar"
    assert entity.domain == "binary_sensor"
    assert entity.name == "Test 1 Is Charging"
    assert entity.state == "on"

    update_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "update_sensor_states",
            "data": [
                {
                    "icon": "mdi:battery-unknown",
                    "state": False,
                    "type": "binary_sensor",
                    "unique_id": "is_charging",
                },
                # This invalid data should not invalidate whole request
                {
                    "type": "binary_sensor",
                    "unique_id": "invalid_state",
                    "invalid": "data",
                },
            ],
        },
    )

    assert update_resp.status == HTTPStatus.OK

    json = await update_resp.json()
    assert json["invalid_state"]["success"] is False

    updated_entity = hass.states.get("binary_sensor.test_1_is_charging")
    assert updated_entity.state == "off"
    assert "foo" not in updated_entity.attributes

    assert len(device_registry.devices) == len(create_registrations)

    # Reload to verify state is restored
    config_entry = hass.config_entries.async_entries("mobile_app")[1]
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    unloaded_entity = hass.states.get("binary_sensor.test_1_is_charging")
    assert unloaded_entity.state == "unavailable"

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    restored_entity = hass.states.get("binary_sensor.test_1_is_charging")
    assert restored_entity.state == updated_entity.state
    assert restored_entity.attributes == updated_entity.attributes


async def test_sensor_must_register(
    hass: HomeAssistant, create_registrations, webhook_client
) -> None:
    """Test that sensors must be registered before updating."""
    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"
    resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "update_sensor_states",
            "data": [
                {"state": True, "type": "binary_sensor", "unique_id": "battery_state"}
            ],
        },
    )

    assert resp.status == HTTPStatus.OK

    json = await resp.json()
    assert json["battery_state"]["success"] is False
    assert json["battery_state"]["error"]["code"] == "not_registered"


async def test_sensor_id_no_dupes(
    hass: HomeAssistant,
    create_registrations,
    webhook_client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a duplicate unique ID in registration updates the sensor."""
    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"

    payload = {
        "type": "register_sensor",
        "data": {
            "attributes": {"foo": "bar"},
            "device_class": "plug",
            "icon": "mdi:power-plug",
            "name": "Is Charging",
            "state": True,
            "type": "binary_sensor",
            "unique_id": "is_charging",
        },
    }

    reg_resp = await webhook_client.post(webhook_url, json=payload)

    assert reg_resp.status == HTTPStatus.CREATED

    reg_json = await reg_resp.json()
    assert reg_json == {"success": True}
    await hass.async_block_till_done()

    assert "Re-register" not in caplog.text

    entity = hass.states.get("binary_sensor.test_1_is_charging")
    assert entity is not None

    assert entity.attributes["device_class"] == "plug"
    assert entity.attributes["icon"] == "mdi:power-plug"
    assert entity.attributes["foo"] == "bar"
    assert entity.domain == "binary_sensor"
    assert entity.name == "Test 1 Is Charging"
    assert entity.state == "on"

    payload["data"]["state"] = False
    dupe_resp = await webhook_client.post(webhook_url, json=payload)

    assert dupe_resp.status == HTTPStatus.CREATED
    dupe_reg_json = await dupe_resp.json()
    assert dupe_reg_json == {"success": True}
    await hass.async_block_till_done()

    assert "Re-register" in caplog.text

    entity = hass.states.get("binary_sensor.test_1_is_charging")
    assert entity is not None

    assert entity.attributes["device_class"] == "plug"
    assert entity.attributes["icon"] == "mdi:power-plug"
    assert entity.attributes["foo"] == "bar"
    assert entity.domain == "binary_sensor"
    assert entity.name == "Test 1 Is Charging"
    assert entity.state == "off"


async def test_register_sensor_no_state(
    hass: HomeAssistant, create_registrations, webhook_client
) -> None:
    """Test that sensors can be registered, when there is no (unknown) state."""
    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"

    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "Is Charging",
                "state": None,
                "type": "binary_sensor",
                "unique_id": "is_charging",
            },
        },
    )

    assert reg_resp.status == HTTPStatus.CREATED

    json = await reg_resp.json()
    assert json == {"success": True}
    await hass.async_block_till_done()

    entity = hass.states.get("binary_sensor.test_1_is_charging")
    assert entity is not None

    assert entity.domain == "binary_sensor"
    assert entity.name == "Test 1 Is Charging"
    assert entity.state == STATE_UNKNOWN

    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "Backup Is Charging",
                "type": "binary_sensor",
                "unique_id": "backup_is_charging",
            },
        },
    )

    assert reg_resp.status == HTTPStatus.CREATED

    json = await reg_resp.json()
    assert json == {"success": True}
    await hass.async_block_till_done()

    entity = hass.states.get("binary_sensor.test_1_backup_is_charging")
    assert entity

    assert entity.domain == "binary_sensor"
    assert entity.name == "Test 1 Backup Is Charging"
    assert entity.state == STATE_UNKNOWN


async def test_update_sensor_no_state(
    hass: HomeAssistant, create_registrations, webhook_client
) -> None:
    """Test that sensors can be updated, when there is no (unknown) state."""
    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"

    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "Is Charging",
                "state": True,
                "type": "binary_sensor",
                "unique_id": "is_charging",
            },
        },
    )

    assert reg_resp.status == HTTPStatus.CREATED

    json = await reg_resp.json()
    assert json == {"success": True}
    await hass.async_block_till_done()

    entity = hass.states.get("binary_sensor.test_1_is_charging")
    assert entity is not None
    assert entity.state == "on"

    update_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "update_sensor_states",
            "data": [
                {"state": None, "type": "binary_sensor", "unique_id": "is_charging"}
            ],
        },
    )

    assert update_resp.status == HTTPStatus.OK

    json = await update_resp.json()
    assert json == {"is_charging": {"success": True}}

    updated_entity = hass.states.get("binary_sensor.test_1_is_charging")
    assert updated_entity.state == STATE_UNKNOWN
