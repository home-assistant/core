"""Tests for KNX integration specific triggers."""
import logging

import pytest

from homeassistant.components import automation
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from .conftest import KNXTestKit

from tests.common import async_mock_service


@pytest.fixture
def calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_telegram_trigger(
    hass: HomeAssistant,
    calls: list[ServiceCall],
    knx: KNXTestKit,
) -> None:
    """Test telegram telegram triggers firing."""
    await knx.setup_integration({})

    # "id" field added to action to test if `trigger_data` passed correctly in `async_attach_trigger`
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                # "catch_all" trigger
                {
                    "trigger": {
                        "platform": "knx.telegram",
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
                        "platform": "knx.telegram",
                        "id": "test-id",
                        "destination": ["1/2/3", "1/2/4"],
                        "group_value_write": True,
                        "group_value_response": False,
                        "group_value_read": False,
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

    # "specific" shall ignore GroupValueRead
    await knx.receive_read("1/2/4")
    assert len(calls) == 1
    test_call = calls.pop()
    assert test_call.data["catch_all"] == "telegram - 1/2/4"
    assert test_call.data["id"] == 0


async def test_remove_telegram_trigger(
    hass: HomeAssistant,
    calls: list[ServiceCall],
    knx: KNXTestKit,
) -> None:
    """Test for removed callback when telegram trigger not used."""
    automation_name = "telegram_trigger_automation"
    await knx.setup_integration({})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "alias": automation_name,
                    "trigger": {
                        "platform": "knx.telegram",
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


async def test_invalid_trigger(
    hass: HomeAssistant,
    knx: KNXTestKit,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid telegram trigger configuration."""
    await knx.setup_integration({})
    caplog.clear()
    with caplog.at_level(logging.ERROR):
        assert await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: [
                    {
                        "trigger": {
                            "platform": "knx.telegram",
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
        await hass.async_block_till_done()
        assert (
            "Unnamed automation failed to setup triggers and has been disabled: "
            "extra keys not allowed @ data['invalid']. Got None"
            in caplog.records[0].message
        )
