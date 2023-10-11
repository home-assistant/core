"""The tests for Monzo device triggers."""

import pytest
from pytest_unordered import unordered

import homeassistant.components.automation as automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.monzo import DOMAIN as MONZO_DOMAIN
from homeassistant.components.monzo.const import (
    MODEL_CURRENT_ACCOUNT,
    MODEL_POT,
    MONZO_EVENT,
)
from homeassistant.components.monzo.device_trigger import async_validate_trigger_config
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    async_capture_events,
    async_get_device_automations,
    async_mock_service,
)


@pytest.fixture
def calls(hass: HomeAssistant):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_get_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we get the expected triggers from a monzo devices."""
    config_entry = MockConfigEntry(domain=MONZO_DOMAIN, data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        model="Current Account",
        identifiers={(MONZO_DOMAIN, 123)},
    )
    entity_registry.async_get_or_create(
        "sensor", MONZO_DOMAIN, "5678", device_id=device_entry.id
    )
    expected_triggers = []
    for event_type in ("transaction.created",):
        expected_triggers.append(
            {
                "platform": "device",
                "account_id": 123,
                "domain": MONZO_DOMAIN,
                "type": event_type,
                "device_id": device_entry.id,
                "metadata": {},
            }
        )

    triggers = [
        trigger
        for trigger in await async_get_device_automations(
            hass, DeviceAutomationType.TRIGGER, device_entry.id
        )
        if trigger["domain"] == MONZO_DOMAIN
    ]
    assert triggers == unordered(expected_triggers)


async def test_if_fires_on_event(
    hass: HomeAssistant,
    calls,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for event triggers firing."""
    mac_address = "12:34:56:AB:CD:EF"
    connection = (dr.CONNECTION_NETWORK_MAC, mac_address)
    config_entry = MockConfigEntry(domain=MONZO_DOMAIN, data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={connection},
        identifiers={(MONZO_DOMAIN, mac_address)},
        model="Current Account",
    )
    entity_registry.async_get_or_create(
        "sensor", MONZO_DOMAIN, "5678", device_id=device_entry.id
    )
    events = async_capture_events(hass, "monzo_event")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "account_id": 123,
                        "domain": MONZO_DOMAIN,
                        "device_id": device_entry.id,
                        "type": "transaction.created",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "{{trigger.event.data.type}} - {{trigger.platform}} - {{trigger.event.data.device_id}}"
                            )
                        },
                    },
                },
            ]
        },
    )

    device = device_registry.async_get_device(connections={connection})
    assert device is not None

    # Fake that the entity is turning on.
    hass.bus.async_fire(
        event_type=MONZO_EVENT,
        event_data={
            "type": "transaction.created",
            ATTR_DEVICE_ID: device.id,
            "account_id": 123,
        },
    )
    await hass.async_block_till_done()
    assert len(events) == 1
    assert len(calls) == 1
    assert calls[0].data["some"] == f"transaction.created - device - {device.id}"


async def test_validation_fails_if_invalid_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test validation of device triggers."""
    config_entry = MockConfigEntry(domain=MONZO_DOMAIN, data={})
    config_entry.add_to_hass(hass)
    pot_device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        model=MODEL_POT,
        identifiers={(MONZO_DOMAIN, 123)},
    )
    account_device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        model=MODEL_CURRENT_ACCOUNT,
        identifiers={(MONZO_DOMAIN, 321)},
    )

    with pytest.raises(InvalidDeviceAutomationConfig, match=".*not found.*"):
        await async_validate_trigger_config(
            hass,
            {
                "device_id": "incorrect",
                "domain": MONZO_DOMAIN,
                "platform": "device",
                "account_id": 42,
                "type": "transaction.created",
            },
        )

    with pytest.raises(InvalidDeviceAutomationConfig, match=".*pot.*"):
        await async_validate_trigger_config(
            hass,
            {
                "device_id": pot_device_entry.id,
                "domain": MONZO_DOMAIN,
                "platform": "device",
                "account_id": 42,
                "type": "transaction.created",
            },
        )

    assert await async_validate_trigger_config(
        hass,
        {
            "device_id": account_device_entry.id,
            "domain": MONZO_DOMAIN,
            "platform": "device",
            "account_id": 42,
            "type": "transaction.created",
        },
    )
