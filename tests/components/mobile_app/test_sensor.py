"""Entity tests for mobile_app."""
from http import HTTPStatus
from unittest.mock import patch

import pytest

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM


@pytest.mark.parametrize(
    ("unit_system", "state_unit", "state1", "state2"),
    (
        (METRIC_SYSTEM, UnitOfTemperature.CELSIUS, "100", "123"),
        (US_CUSTOMARY_SYSTEM, UnitOfTemperature.FAHRENHEIT, "212", "253"),
    ),
)
async def test_sensor(
    hass: HomeAssistant,
    create_registrations,
    webhook_client,
    unit_system,
    state_unit,
    state1,
    state2,
) -> None:
    """Test that sensors can be registered and updated."""
    hass.config.units = unit_system

    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"

    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "attributes": {"foo": "bar"},
                "device_class": "temperature",
                "icon": "mdi:battery",
                "name": "Battery Temperature",
                "state": 100,
                "type": "sensor",
                "entity_category": "diagnostic",
                "unique_id": "battery_temp",
                "state_class": "total",
                "unit_of_measurement": UnitOfTemperature.CELSIUS,
            },
        },
    )

    assert reg_resp.status == HTTPStatus.CREATED

    json = await reg_resp.json()
    assert json == {"success": True}
    await hass.async_block_till_done()

    entity = hass.states.get("sensor.test_1_battery_temperature")
    assert entity is not None

    assert entity.attributes["device_class"] == "temperature"
    assert entity.attributes["icon"] == "mdi:battery"
    # unit of temperature sensor is automatically converted to the system UoM
    assert entity.attributes["unit_of_measurement"] == state_unit
    assert entity.attributes["foo"] == "bar"
    assert entity.attributes["state_class"] == "total"
    assert entity.domain == "sensor"
    assert entity.name == "Test 1 Battery Temperature"
    assert entity.state == state1

    assert (
        er.async_get(hass)
        .async_get("sensor.test_1_battery_temperature")
        .entity_category
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
                    "unique_id": "battery_temp",
                },
                # This invalid data should not invalidate whole request
                {"type": "sensor", "unique_id": "invalid_state", "invalid": "data"},
            ],
        },
    )

    assert update_resp.status == HTTPStatus.OK

    json = await update_resp.json()
    assert json["invalid_state"]["success"] is False

    updated_entity = hass.states.get("sensor.test_1_battery_temperature")
    assert updated_entity.state == state2
    assert "foo" not in updated_entity.attributes

    dev_reg = dr.async_get(hass)
    assert len(dev_reg.devices) == len(create_registrations)

    # Reload to verify state is restored
    config_entry = hass.config_entries.async_entries("mobile_app")[1]
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    unloaded_entity = hass.states.get("sensor.test_1_battery_temperature")
    assert unloaded_entity.state == STATE_UNAVAILABLE

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    restored_entity = hass.states.get("sensor.test_1_battery_temperature")
    assert restored_entity.state == updated_entity.state
    assert restored_entity.attributes == updated_entity.attributes


@pytest.mark.parametrize(
    ("unique_id", "unit_system", "state_unit", "state1", "state2"),
    (
        ("battery_temperature", METRIC_SYSTEM, UnitOfTemperature.CELSIUS, "100", "123"),
        (
            "battery_temperature",
            US_CUSTOMARY_SYSTEM,
            UnitOfTemperature.FAHRENHEIT,
            "212",
            "253",
        ),
        # The unique_id doesn't match that of the mobile app's battery temperature sensor
        (
            "battery_temp",
            US_CUSTOMARY_SYSTEM,
            UnitOfTemperature.FAHRENHEIT,
            "212",
            "123",
        ),
    ),
)
async def test_sensor_migration(
    hass: HomeAssistant,
    create_registrations,
    webhook_client,
    unique_id,
    unit_system,
    state_unit,
    state1,
    state2,
) -> None:
    """Test migration to RestoreSensor."""
    hass.config.units = unit_system

    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"

    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "attributes": {"foo": "bar"},
                "device_class": "temperature",
                "icon": "mdi:battery",
                "name": "Battery Temperature",
                "state": 100,
                "type": "sensor",
                "entity_category": "diagnostic",
                "unique_id": unique_id,
                "state_class": "total",
                "unit_of_measurement": UnitOfTemperature.CELSIUS,
            },
        },
    )

    assert reg_resp.status == HTTPStatus.CREATED

    json = await reg_resp.json()
    assert json == {"success": True}
    await hass.async_block_till_done()

    entity = hass.states.get("sensor.test_1_battery_temperature")
    assert entity is not None

    assert entity.attributes["device_class"] == "temperature"
    assert entity.attributes["icon"] == "mdi:battery"
    # unit of temperature sensor is automatically converted to the system UoM
    assert entity.attributes["unit_of_measurement"] == state_unit
    assert entity.attributes["foo"] == "bar"
    assert entity.attributes["state_class"] == "total"
    assert entity.domain == "sensor"
    assert entity.name == "Test 1 Battery Temperature"
    assert entity.state == state1

    # Reload to verify state is restored
    config_entry = hass.config_entries.async_entries("mobile_app")[1]
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    unloaded_entity = hass.states.get("sensor.test_1_battery_temperature")
    assert unloaded_entity.state == STATE_UNAVAILABLE

    # Simulate migration to RestoreSensor
    with patch(
        "homeassistant.helpers.restore_state.RestoreEntity.async_get_last_extra_data",
        return_value=None,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    restored_entity = hass.states.get("sensor.test_1_battery_temperature")
    assert restored_entity.state == "unknown"
    assert restored_entity.attributes == entity.attributes

    # Test unit conversion is working
    update_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "update_sensor_states",
            "data": [
                {
                    "icon": "mdi:battery-unknown",
                    "state": 123,
                    "type": "sensor",
                    "unique_id": unique_id,
                },
            ],
        },
    )

    assert update_resp.status == HTTPStatus.OK

    updated_entity = hass.states.get("sensor.test_1_battery_temperature")
    assert updated_entity.state == state2
    assert "foo" not in updated_entity.attributes


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
            "data": [{"state": 123, "type": "sensor", "unique_id": "battery_state"}],
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
    ("device_class", "native_value", "state_value"),
    [
        (SensorDeviceClass.DATE, "2021-11-18", "2021-11-18"),
        (
            SensorDeviceClass.TIMESTAMP,
            "2021-11-18T20:25:00+00:00",
            "2021-11-18T20:25:00+00:00",
        ),
        (
            SensorDeviceClass.TIMESTAMP,
            "2021-11-18 20:25:00+01:00",
            "2021-11-18T19:25:00+00:00",
        ),
        (
            SensorDeviceClass.TIMESTAMP,
            "unavailable",
            STATE_UNAVAILABLE,
        ),
        (
            SensorDeviceClass.TIMESTAMP,
            "unknown",
            STATE_UNKNOWN,
        ),
    ],
)
async def test_sensor_datetime(
    hass: HomeAssistant,
    create_registrations,
    webhook_client,
    device_class,
    native_value,
    state_value,
) -> None:
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


async def test_default_disabling_entity(
    hass: HomeAssistant, create_registrations, webhook_client
) -> None:
    """Test that sensors can be disabled by default upon registration."""
    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"

    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "Battery State",
                "type": "sensor",
                "unique_id": "battery_state",
                "disabled": True,
            },
        },
    )

    assert reg_resp.status == HTTPStatus.CREATED

    json = await reg_resp.json()
    assert json == {"success": True}
    await hass.async_block_till_done()

    entity = hass.states.get("sensor.test_1_battery_state")
    assert entity is None

    assert (
        er.async_get(hass).async_get("sensor.test_1_battery_state").disabled_by
        == er.RegistryEntryDisabler.INTEGRATION
    )


async def test_updating_disabled_sensor(
    hass: HomeAssistant, create_registrations, webhook_client
) -> None:
    """Test that sensors return error if disabled in instance."""
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

    er.async_get(hass).async_update_entity(
        "sensor.test_1_battery_state", disabled_by=er.RegistryEntryDisabler.USER
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
            ],
        },
    )

    assert update_resp.status == HTTPStatus.OK

    json = await update_resp.json()
    assert json["battery_state"]["success"] is True
    assert json["battery_state"]["is_disabled"] is True
