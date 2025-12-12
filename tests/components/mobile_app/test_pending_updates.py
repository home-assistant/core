"""Tests for mobile_app pending updates functionality."""

from http import HTTPStatus
from typing import Any

from aiohttp.test_utils import TestClient

from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_pending_update_applied_when_entity_enabled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
    webhook_client: TestClient,
) -> None:
    """Test that updates sent while disabled are applied when entity is re-enabled."""
    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"

    # Register a sensor
    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "Battery State",
                "state": 100,
                "type": "sensor",
                "unique_id": "battery_state",
                "unit_of_measurement": PERCENTAGE,
            },
        },
    )

    assert reg_resp.status == HTTPStatus.CREATED
    await hass.async_block_till_done()

    entity = hass.states.get("sensor.test_1_battery_state")
    assert entity is not None
    assert entity.state == "100"

    # Disable the entity
    entity_registry.async_update_entity(
        "sensor.test_1_battery_state", disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()

    # Send update while disabled
    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "Battery State",
                "state": 50,
                "type": "sensor",
                "unique_id": "battery_state",
                "unit_of_measurement": PERCENTAGE,
            },
        },
    )

    assert reg_resp.status == HTTPStatus.CREATED
    await hass.async_block_till_done()

    # Re-enable the entity
    entity_registry.async_update_entity("sensor.test_1_battery_state", disabled_by=None)

    # Reload the config entry to trigger entity re-creation
    config_entry = hass.config_entries.async_entries("mobile_app")[1]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify the update sent while disabled was applied
    entity = hass.states.get("sensor.test_1_battery_state")
    assert entity is not None
    assert entity.state == "50"


async def test_pending_update_with_attributes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
    webhook_client: TestClient,
) -> None:
    """Test that pending updates preserve all attributes."""
    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"

    # Register a sensor
    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "Battery State",
                "state": 100,
                "type": "sensor",
                "unique_id": "battery_state",
                "attributes": {"charging": True, "voltage": 4.2},
                "icon": "mdi:battery-charging",
            },
        },
    )

    assert reg_resp.status == HTTPStatus.CREATED
    await hass.async_block_till_done()

    # Disable the entity
    entity_registry.async_update_entity(
        "sensor.test_1_battery_state", disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()

    # Send update with different attributes while disabled
    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "Battery State",
                "state": 50,
                "type": "sensor",
                "unique_id": "battery_state",
                "attributes": {"charging": False, "voltage": 3.7},
                "icon": "mdi:battery-50",
            },
        },
    )

    assert reg_resp.status == HTTPStatus.CREATED
    await hass.async_block_till_done()

    # Re-enable the entity
    entity_registry.async_update_entity("sensor.test_1_battery_state", disabled_by=None)

    # Reload the config entry
    config_entry = hass.config_entries.async_entries("mobile_app")[1]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify all attributes were applied
    entity = hass.states.get("sensor.test_1_battery_state")
    assert entity is not None
    assert entity.state == "50"
    assert entity.attributes["charging"] is False
    assert entity.attributes["voltage"] == 3.7
    assert entity.attributes["icon"] == "mdi:battery-50"


async def test_pending_update_overwritten_by_newer_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
    webhook_client: TestClient,
) -> None:
    """Test that newer pending updates overwrite older ones."""
    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"

    # Register a sensor
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
    await hass.async_block_till_done()

    # Disable the entity
    entity_registry.async_update_entity(
        "sensor.test_1_battery_state", disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()

    # Send first update while disabled
    await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "Battery State",
                "state": 75,
                "type": "sensor",
                "unique_id": "battery_state",
            },
        },
    )
    await hass.async_block_till_done()

    # Send second update while still disabled - should overwrite
    await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "Battery State",
                "state": 25,
                "type": "sensor",
                "unique_id": "battery_state",
            },
        },
    )
    await hass.async_block_till_done()

    # Re-enable the entity
    entity_registry.async_update_entity("sensor.test_1_battery_state", disabled_by=None)

    # Reload the config entry
    config_entry = hass.config_entries.async_entries("mobile_app")[1]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify the latest update was applied (25, not 75)
    entity = hass.states.get("sensor.test_1_battery_state")
    assert entity is not None
    assert entity.state == "25"


async def test_pending_update_not_stored_on_enabled_entities(
    hass: HomeAssistant,
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
    webhook_client: TestClient,
) -> None:
    """Test that enabled entities receive updates immediately."""
    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"

    # Register a sensor
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
    await hass.async_block_till_done()

    entity = hass.states.get("sensor.test_1_battery_state")
    assert entity is not None
    assert entity.state == "100"

    # Send update while enabled - should apply immediately
    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "Battery State",
                "state": 50,
                "type": "sensor",
                "unique_id": "battery_state",
            },
        },
    )

    assert reg_resp.status == HTTPStatus.CREATED
    await hass.async_block_till_done()

    # Verify update was applied immediately
    entity = hass.states.get("sensor.test_1_battery_state")
    assert entity is not None
    assert entity.state == "50"


async def test_pending_update_fallback_to_restore_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
    webhook_client: TestClient,
) -> None:
    """Test that restored state is used when no pending update exists."""
    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"

    # Register a sensor
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
    await hass.async_block_till_done()

    entity = hass.states.get("sensor.test_1_battery_state")
    assert entity is not None
    assert entity.state == "100"

    # Update to a new state
    await webhook_client.post(
        webhook_url,
        json={
            "type": "update_sensor_states",
            "data": [
                {
                    "state": 75,
                    "type": "sensor",
                    "unique_id": "battery_state",
                }
            ],
        },
    )
    await hass.async_block_till_done()

    entity = hass.states.get("sensor.test_1_battery_state")
    assert entity is not None
    assert entity.state == "75"

    # Reload without pending updates
    config_entry = hass.config_entries.async_entries("mobile_app")[1]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify restored state was used
    entity = hass.states.get("sensor.test_1_battery_state")
    assert entity is not None
    assert entity.state == "75"


async def test_multiple_pending_updates_for_different_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
    webhook_client: TestClient,
) -> None:
    """Test that multiple sensors can be updated while disabled and applied when re-enabled."""
    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"

    # Register two sensors
    for unique_id, state in (("battery_state", 100), ("battery_temp", 25)):
        reg_resp = await webhook_client.post(
            webhook_url,
            json={
                "type": "register_sensor",
                "data": {
                    "name": unique_id.replace("_", " ").title(),
                    "state": state,
                    "type": "sensor",
                    "unique_id": unique_id,
                },
            },
        )
        assert reg_resp.status == HTTPStatus.CREATED

    await hass.async_block_till_done()

    # Disable both entities
    entity_registry.async_update_entity(
        "sensor.test_1_battery_state", disabled_by=er.RegistryEntryDisabler.USER
    )
    entity_registry.async_update_entity(
        "sensor.test_1_battery_temp", disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()

    # Send updates for both while disabled
    await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "Battery State",
                "state": 50,
                "type": "sensor",
                "unique_id": "battery_state",
            },
        },
    )

    await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "Battery Temp",
                "state": 30,
                "type": "sensor",
                "unique_id": "battery_temp",
            },
        },
    )
    await hass.async_block_till_done()

    # Re-enable both entities
    entity_registry.async_update_entity("sensor.test_1_battery_state", disabled_by=None)
    entity_registry.async_update_entity("sensor.test_1_battery_temp", disabled_by=None)

    # Reload the config entry
    config_entry = hass.config_entries.async_entries("mobile_app")[1]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify both updates sent while disabled were applied
    battery_state = hass.states.get("sensor.test_1_battery_state")
    battery_temp = hass.states.get("sensor.test_1_battery_temp")

    assert battery_state is not None
    assert battery_state.state == "50"
    assert battery_temp is not None
    assert battery_temp.state == "30"


async def test_update_sensor_states_with_pending_updates(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
    webhook_client: TestClient,
) -> None:
    """Test that update_sensor_states updates are applied when entity is re-enabled."""
    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"

    # Register a sensor
    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "Battery State",
                "state": 100,
                "type": "sensor",
                "unique_id": "battery_state",
                "unit_of_measurement": PERCENTAGE,
            },
        },
    )

    assert reg_resp.status == HTTPStatus.CREATED
    await hass.async_block_till_done()

    entity = hass.states.get("sensor.test_1_battery_state")
    assert entity is not None
    assert entity.state == "100"

    # Disable the entity
    entity_registry.async_update_entity(
        "sensor.test_1_battery_state", disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()

    # Use update_sensor_states while disabled
    resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "update_sensor_states",
            "data": [
                {
                    "state": 75,
                    "type": "sensor",
                    "unique_id": "battery_state",
                }
            ],
        },
    )

    assert resp.status == HTTPStatus.OK
    await hass.async_block_till_done()

    # Re-enable the entity
    entity_registry.async_update_entity("sensor.test_1_battery_state", disabled_by=None)

    # Reload the config entry to trigger entity re-creation
    config_entry = hass.config_entries.async_entries("mobile_app")[1]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify the update sent while disabled was applied
    entity = hass.states.get("sensor.test_1_battery_state")
    assert entity is not None
    assert entity.state == "75"


async def test_update_sensor_states_always_stores_pending(
    hass: HomeAssistant,
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
    webhook_client: TestClient,
) -> None:
    """Test that update_sensor_states applies updates to enabled entities."""
    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"

    # Register a sensor
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
    await hass.async_block_till_done()

    entity = hass.states.get("sensor.test_1_battery_state")
    assert entity is not None
    assert entity.state == "100"

    # Use update_sensor_states while enabled
    resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "update_sensor_states",
            "data": [
                {
                    "state": 50,
                    "type": "sensor",
                    "unique_id": "battery_state",
                }
            ],
        },
    )

    assert resp.status == HTTPStatus.OK
    await hass.async_block_till_done()

    # Verify update was applied
    entity = hass.states.get("sensor.test_1_battery_state")
    assert entity is not None
    assert entity.state == "50"


async def test_binary_sensor_pending_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    create_registrations: tuple[dict[str, Any], dict[str, Any]],
    webhook_client: TestClient,
) -> None:
    """Test that binary sensor updates are applied when entity is re-enabled."""
    webhook_id = create_registrations[1]["webhook_id"]
    webhook_url = f"/api/webhook/{webhook_id}"

    # Register a binary sensor
    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "Motion Detected",
                "state": False,
                "type": "binary_sensor",
                "unique_id": "motion_sensor",
            },
        },
    )

    assert reg_resp.status == HTTPStatus.CREATED
    await hass.async_block_till_done()

    entity = hass.states.get("binary_sensor.test_1_motion_detected")
    assert entity is not None
    assert entity.state == "off"

    # Disable the entity
    entity_registry.async_update_entity(
        "binary_sensor.test_1_motion_detected",
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    await hass.async_block_till_done()

    # Send update while disabled
    reg_resp = await webhook_client.post(
        webhook_url,
        json={
            "type": "register_sensor",
            "data": {
                "name": "Motion Detected",
                "state": True,
                "type": "binary_sensor",
                "unique_id": "motion_sensor",
            },
        },
    )

    assert reg_resp.status == HTTPStatus.CREATED
    await hass.async_block_till_done()

    # Re-enable the entity
    entity_registry.async_update_entity(
        "binary_sensor.test_1_motion_detected", disabled_by=None
    )

    # Reload the config entry
    config_entry = hass.config_entries.async_entries("mobile_app")[1]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify the update sent while disabled was applied
    entity = hass.states.get("binary_sensor.test_1_motion_detected")
    assert entity is not None
    assert entity.state == "on"
