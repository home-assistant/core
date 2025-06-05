"""The tests for Blue Current device triggers."""

from pytest_unordered import unordered

from homeassistant.components import automation
from homeassistant.components.blue_current import DOMAIN
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_get_device_automations


async def test_get_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test we get the expected triggers from a bluecurrent."""
    config_entry.add_to_hass(hass)
    evse_id = "101"

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, evse_id)},
    )
    entity_registry.async_get_or_create(
        DOMAIN, "activity", "101", device_id=device_entry.id
    )
    entity_registry.async_get_or_create(
        DOMAIN, "vehicle_status", "101", device_id=device_entry.id
    )
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "entity_id": "sensor.activity_101",
            "type": "available",
            "metadata": {},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "entity_id": "sensor.activity_101",
            "type": "charging",
            "metadata": {},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "entity_id": "sensor.activity_101",
            "type": "unavailable",
            "metadata": {},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "entity_id": "sensor.activity_101",
            "type": "error",
            "metadata": {},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "entity_id": "sensor.activity_101",
            "type": "offline",
            "metadata": {},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "entity_id": "sensor.vehicle_status_101",
            "type": "standby",
            "metadata": {},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "entity_id": "sensor.vehicle_status_101",
            "type": "vehicle_detected",
            "metadata": {},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "entity_id": "sensor.vehicle_status_101",
            "type": "ready",
            "metadata": {},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "entity_id": "sensor.vehicle_status_101",
            "type": "no_power",
            "metadata": {},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "entity_id": "sensor.vehicle_status_101",
            "type": "vehicle_error",
            "metadata": {},
        },
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    unordered(triggers, expected_triggers)


async def test_if_activity_fires_on_state_change(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    service_calls: list[ServiceCall],
) -> None:
    """Test for blue current activity trigger firing."""
    evse_id = "101"

    config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, evse_id)},
    )
    entity_registry.async_get_or_create(
        DOMAIN, "activity", "101", device_id=device_entry.id
    )

    hass.states.async_set("sensor.activity_101", "unavailable")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "entity_id": "sensor.activity_101",
                        "type": activity_type,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": (activity_type)},
                    },
                }
                for activity_type in (
                    "available",
                    "charging",
                    "unavailable",
                    "error",
                    "offline",
                )
            ]
        },
    )

    hass.states.async_set("sensor.activity_101", "charging")

    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data["some"] == "charging"

    hass.states.async_set("sensor.activity_101", "available")
    await hass.async_block_till_done()
    assert len(service_calls) == 2
    assert service_calls[1].data["some"] == "available"

    hass.states.async_set("sensor.activity_101", "error")
    await hass.async_block_till_done()
    assert len(service_calls) == 3
    assert service_calls[2].data["some"] == "error"

    hass.states.async_set("sensor.activity_101", "offline")
    await hass.async_block_till_done()
    assert len(service_calls) == 4
    assert service_calls[3].data["some"] == "offline"

    hass.states.async_set("sensor.activity_101", "unavailable")
    await hass.async_block_till_done()
    assert len(service_calls) == 5
    assert service_calls[4].data["some"] == "unavailable"


async def test_if_vehicle_status_fires_on_state_change(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    service_calls: list[ServiceCall],
) -> None:
    """Test for blue current vehicle_status trigger firing."""
    evse_id = "101"

    config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, evse_id)},
    )
    entity_registry.async_get_or_create(
        DOMAIN, "activity", "101", device_id=device_entry.id
    )

    hass.states.async_set("sensor.vehicle_status_101", "vehicle_status")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "entity_id": "sensor.vehicle_status_101",
                        "type": vehicle_status_type,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": (vehicle_status_type)},
                    },
                }
                for vehicle_status_type in (
                    "standby",
                    "vehicle_detected",
                    "ready",
                    "no_power",
                    "vehicle_error",
                )
            ]
        },
    )

    hass.states.async_set("sensor.vehicle_status_101", "standby")
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data["some"] == "standby"

    hass.states.async_set("sensor.vehicle_status_101", "vehicle_detected")
    await hass.async_block_till_done()
    assert len(service_calls) == 2
    assert service_calls[1].data["some"] == "vehicle_detected"

    hass.states.async_set("sensor.vehicle_status_101", "ready")
    await hass.async_block_till_done()
    assert len(service_calls) == 3
    assert service_calls[2].data["some"] == "ready"

    hass.states.async_set("sensor.vehicle_status_101", "no_power")
    await hass.async_block_till_done()
    assert len(service_calls) == 4
    assert service_calls[3].data["some"] == "no_power"

    hass.states.async_set("sensor.vehicle_status_101", "vehicle_error")
    await hass.async_block_till_done()
    assert len(service_calls) == 5
    assert service_calls[4].data["some"] == "vehicle_error"
