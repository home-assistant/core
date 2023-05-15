"""Tests for KNX device triggers."""
import pytest
import voluptuous_serialize

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.knx import DOMAIN, device_trigger
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
                            "catch_all": ("telegram - {{ trigger.destination }}")
                        },
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "type": "telegram",
                        "Addresses": ["1/2/3", "1/2/4"],
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "specific": ("telegram - {{ trigger.destination }}")
                        },
                    },
                },
            ]
        },
    )

    await knx.receive_write("0/0/1", (0x03, 0x2F))
    assert len(calls) == 1
    assert calls.pop().data["catch_all"] == "telegram - 0/0/1"

    await knx.receive_write("1/2/4", (0x03, 0x2F))
    assert len(calls) == 2
    assert calls.pop().data["specific"] == "telegram - 1/2/4"
    assert calls.pop().data["catch_all"] == "telegram - 1/2/4"


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
            "name": "Addresses",
            "optional": True,
            "selector": {
                "select": {
                    "custom_value": True,
                    "mode": "dropdown",
                    "multiple": True,
                    "options": [],
                },
            },
        }
    ]
