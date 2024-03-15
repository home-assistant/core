"""Tests for KNX device triggers."""

import pytest
import voluptuous_serialize

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.knx import DOMAIN, device_trigger
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import KNXTestKit

from tests.common import async_get_device_automations, async_mock_service


@pytest.fixture
def calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_get_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    knx: KNXTestKit,
) -> None:
    """Test we get the expected triggers from knx."""
    await knx.setup_integration({})
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, f"_{knx.mock_config_entry.entry_id}_interface")}
    )
    expected_trigger = {
        "platform": "device",
        "domain": DOMAIN,
        "device_id": device_entry.id,
        "type": "telegram",
        "metadata": {},
    }
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert expected_trigger in triggers


async def test_if_fires_on_telegram(
    hass: HomeAssistant,
    calls: list[ServiceCall],
    device_registry: dr.DeviceRegistry,
    knx: KNXTestKit,
) -> None:
    """Test for telegram triggers firing."""
    await knx.setup_integration({})
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, f"_{knx.mock_config_entry.entry_id}_interface")}
    )

    # "id" field added to action to test if `trigger_data` passed correctly in `async_attach_trigger`
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
                        "type": "telegram",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "catch_all": ("telegram - {{ trigger.destination }}"),
                            "id": (" {{ trigger.id }}"),
                        },
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "type": "telegram",
                        "destination": ["1/2/3", "1/2/4"],
                        "id": "test-id",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "specific": ("telegram - {{ trigger.destination }}"),
                            "id": (" {{ trigger.id }}"),
                        },
                    },
                },
            ]
        },
    )

    await knx.receive_write("0/0/1", (0x03, 0x2F))
    assert len(calls) == 1
    test_call = calls.pop()
    assert test_call.data["catch_all"] == "telegram - 0/0/1"
    assert test_call.data["id"] == 0

    await knx.receive_write("1/2/4", (0x03, 0x2F))
    assert len(calls) == 2
    test_call = calls.pop()
    assert test_call.data["specific"] == "telegram - 1/2/4"
    assert test_call.data["id"] == "test-id"
    test_call = calls.pop()
    assert test_call.data["catch_all"] == "telegram - 1/2/4"
    assert test_call.data["id"] == 0


async def test_remove_device_trigger(
    hass: HomeAssistant,
    calls: list[ServiceCall],
    device_registry: dr.DeviceRegistry,
    knx: KNXTestKit,
) -> None:
    """Test for removed callback when device trigger not used."""
    automation_name = "telegram_trigger_automation"
    await knx.setup_integration({})
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, f"_{knx.mock_config_entry.entry_id}_interface")}
    )
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "alias": automation_name,
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "type": "telegram",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "catch_all": ("telegram - {{ trigger.destination }}")
                        },
                    },
                }
            ]
        },
    )

    await knx.receive_write("0/0/1", (0x03, 0x2F))
    assert len(calls) == 1
    assert calls.pop().data["catch_all"] == "telegram - 0/0/1"

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: f"automation.{automation_name}"},
        blocking=True,
    )
    await knx.receive_write("0/0/1", (0x03, 0x2F))
    assert len(calls) == 0


async def test_get_trigger_capabilities_node_status(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    knx: KNXTestKit,
) -> None:
    """Test we get the expected capabilities from a node_status trigger."""
    await knx.setup_integration({})
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, f"_{knx.mock_config_entry.entry_id}_interface")}
    )

    capabilities = await device_trigger.async_get_trigger_capabilities(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "type": "telegram",
        },
    )
    assert capabilities and "extra_fields" in capabilities

    assert voluptuous_serialize.convert(
        capabilities["extra_fields"], custom_serializer=cv.custom_serializer
    ) == [
        {
            "name": "destination",
            "optional": True,
            "selector": {
                "select": {
                    "custom_value": True,
                    "mode": "dropdown",
                    "multiple": True,
                    "options": [],
                    "sort": False,
                },
            },
        }
    ]
