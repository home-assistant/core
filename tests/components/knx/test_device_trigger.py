"""Tests for KNX device triggers."""

import logging

import pytest
import voluptuous_serialize

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.knx import DOMAIN, device_trigger
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import KNXTestKit

from tests.common import async_get_device_automations


async def test_if_fires_on_telegram(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    device_registry: dr.DeviceRegistry,
    knx: KNXTestKit,
) -> None:
    """Test telegram device triggers firing."""
    await knx.setup_integration()
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, f"_{knx.mock_config_entry.entry_id}_interface")}
    )

    # "id" field added to action to test if `trigger_data` passed correctly in `async_attach_trigger`
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                # "catch_all" trigger
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "type": "telegram",
                        "group_value_write": True,
                        "group_value_response": True,
                        "group_value_read": True,
                        "incoming": True,
                        "outgoing": True,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "catch_all": ("telegram - {{ trigger.destination }}"),
                            "id": (" {{ trigger.id }}"),
                        },
                    },
                },
                # "specific" trigger
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "id": "test-id",
                        "type": "telegram",
                        "destination": [
                            "1/2/3",
                            "1/516",  # "1/516" -> "1/2/4" in 2level format
                        ],
                        "group_value_write": True,
                        "group_value_response": False,
                        "group_value_read": False,
                        "incoming": True,
                        "outgoing": False,
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

    # "specific" shall ignore destination address
    await knx.receive_write("0/0/1", (0x03, 0x2F))
    assert len(service_calls) == 1
    test_call = service_calls.pop()
    assert test_call.data["catch_all"] == "telegram - 0/0/1"
    assert test_call.data["id"] == 0

    await knx.receive_write("1/2/4", (0x03, 0x2F))
    assert len(service_calls) == 2
    test_call = service_calls.pop()
    assert test_call.data["specific"] == "telegram - 1/2/4"
    assert test_call.data["id"] == "test-id"
    test_call = service_calls.pop()
    assert test_call.data["catch_all"] == "telegram - 1/2/4"
    assert test_call.data["id"] == 0

    # "specific" shall ignore GroupValueRead
    await knx.receive_read("1/2/4")
    assert len(service_calls) == 1
    test_call = service_calls.pop()
    assert test_call.data["catch_all"] == "telegram - 1/2/4"
    assert test_call.data["id"] == 0


async def test_default_if_fires_on_telegram(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    device_registry: dr.DeviceRegistry,
    knx: KNXTestKit,
) -> None:
    """Test default telegram device triggers firing."""
    # by default (without a user changing any) extra_fields are not added to the trigger and
    # pre 2024.2 device triggers did only support "destination" field so they didn't have
    # "group_value_write", "group_value_response", "group_value_read", "incoming", "outgoing"
    await knx.setup_integration()
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, f"_{knx.mock_config_entry.entry_id}_interface")}
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                # "catch_all" trigger
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
                # "specific" trigger
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
    assert len(service_calls) == 1
    test_call = service_calls.pop()
    assert test_call.data["catch_all"] == "telegram - 0/0/1"
    assert test_call.data["id"] == 0

    await knx.receive_write("1/2/4", (0x03, 0x2F))
    assert len(service_calls) == 2
    test_call = service_calls.pop()
    assert test_call.data["specific"] == "telegram - 1/2/4"
    assert test_call.data["id"] == "test-id"
    test_call = service_calls.pop()
    assert test_call.data["catch_all"] == "telegram - 1/2/4"
    assert test_call.data["id"] == 0

    # "specific" shall catch GroupValueRead as it is not set explicitly
    await knx.receive_read("1/2/4")
    assert len(service_calls) == 2
    test_call = service_calls.pop()
    assert test_call.data["specific"] == "telegram - 1/2/4"
    assert test_call.data["id"] == "test-id"
    test_call = service_calls.pop()
    assert test_call.data["catch_all"] == "telegram - 1/2/4"
    assert test_call.data["id"] == 0


async def test_remove_device_trigger(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    device_registry: dr.DeviceRegistry,
    knx: KNXTestKit,
) -> None:
    """Test for removed callback when device trigger not used."""
    automation_name = "telegram_trigger_automation"
    await knx.setup_integration()
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
    assert len(service_calls) == 1
    assert service_calls.pop().data["catch_all"] == "telegram - 0/0/1"

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: f"automation.{automation_name}"},
        blocking=True,
    )
    assert len(service_calls) == 1

    await knx.receive_write("0/0/1", (0x03, 0x2F))
    assert len(service_calls) == 1


async def test_get_triggers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    knx: KNXTestKit,
) -> None:
    """Test we get the expected device triggers from knx."""
    await knx.setup_integration()
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


async def test_get_trigger_capabilities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    knx: KNXTestKit,
) -> None:
    """Test we get the expected capabilities telegram device trigger."""
    await knx.setup_integration()
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
        },
        {
            "name": "group_value_write",
            "optional": True,
            "default": True,
            "selector": {
                "boolean": {},
            },
        },
        {
            "name": "group_value_response",
            "optional": True,
            "default": True,
            "selector": {
                "boolean": {},
            },
        },
        {
            "name": "group_value_read",
            "optional": True,
            "default": True,
            "selector": {
                "boolean": {},
            },
        },
        {
            "name": "incoming",
            "optional": True,
            "default": True,
            "selector": {
                "boolean": {},
            },
        },
        {
            "name": "outgoing",
            "optional": True,
            "default": True,
            "selector": {
                "boolean": {},
            },
        },
    ]


async def test_invalid_device_trigger(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    knx: KNXTestKit,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid telegram device trigger configuration."""
    await knx.setup_integration()
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, f"_{knx.mock_config_entry.entry_id}_interface")}
    )
    caplog.clear()
    with caplog.at_level(logging.ERROR):
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
                            "invalid": True,
                        },
                        "action": {
                            "service": "test.automation",
                            "data_template": {
                                "catch_all": ("telegram - {{ trigger.destination }}"),
                                "id": (" {{ trigger.id }}"),
                            },
                        },
                    },
                ]
            },
        )
        assert (
            "Unnamed automation failed to setup triggers and has been disabled: "
            "extra keys not allowed @ data['invalid']. Got None"
            in caplog.records[0].message
        )


async def test_invalid_trigger_configuration(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    knx: KNXTestKit,
) -> None:
    """Test invalid telegram device trigger configuration at attach_trigger."""
    await knx.setup_integration()
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, f"_{knx.mock_config_entry.entry_id}_interface")}
    )
    # After changing the config in async_attach_trigger, the config is validated again
    # against the integration trigger. This test checks if this validation works.
    with pytest.raises(InvalidDeviceAutomationConfig):
        await device_trigger.async_attach_trigger(
            hass,
            {
                "platform": "device",
                "domain": DOMAIN,
                "device_id": device_entry.id,
                "type": "telegram",
                "group_value_write": "invalid",
            },
            None,
            {},
        )
