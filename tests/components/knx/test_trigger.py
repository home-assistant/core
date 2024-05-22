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
    """Test telegram triggers firing."""
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
                        "destination": ["1/2/3", 2564],  # 2564 -> "1/2/4" in raw format
                        "group_value_write": True,
                        "group_value_response": False,
                        "group_value_read": False,
                        "incoming": True,
                        "outgoing": True,
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


@pytest.mark.parametrize(
    ("payload", "type_option", "expected_value", "expected_unit"),
    [
        ((0x4C,), {"type": "percent"}, 30, "%"),
        ((0x03,), {}, None, None),  # "dpt" omitted defaults to None
        ((0x0C, 0x1A), {"type": "temperature"}, 21.00, "°C"),
    ],
)
async def test_telegram_trigger_dpt_option(
    hass: HomeAssistant,
    calls: list[ServiceCall],
    knx: KNXTestKit,
    payload: tuple[int, ...],
    type_option: dict[str, bool],
    expected_value: int | None,
    expected_unit: str | None,
) -> None:
    """Test telegram trigger type option."""
    await knx.setup_integration({})
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                # "catch_all" trigger
                {
                    "trigger": {
                        "platform": "knx.telegram",
                        **type_option,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "catch_all": ("telegram - {{ trigger.destination }}"),
                            "trigger": (" {{ trigger }}"),
                        },
                    },
                },
            ]
        },
    )
    await knx.receive_write("0/0/1", payload)

    assert len(calls) == 1
    test_call = calls.pop()
    assert test_call.data["catch_all"] == "telegram - 0/0/1"
    assert test_call.data["trigger"]["value"] == expected_value
    assert test_call.data["trigger"]["unit"] == expected_unit

    await knx.receive_read("0/0/1")

    assert len(calls) == 1
    test_call = calls.pop()
    assert test_call.data["catch_all"] == "telegram - 0/0/1"
    assert test_call.data["trigger"]["value"] is None
    assert test_call.data["trigger"]["unit"] is None


@pytest.mark.parametrize(
    "group_value_options",
    [
        {
            "group_value_write": True,
            "group_value_response": True,
            "group_value_read": False,
        },
        {
            "group_value_write": False,
            "group_value_response": False,
            "group_value_read": True,
        },
        {
            # "group_value_write": True,  # omitted defaults to True
            "group_value_response": False,
            "group_value_read": False,
        },
    ],
)
@pytest.mark.parametrize(
    "direction_options",
    [
        {
            "incoming": True,
            "outgoing": True,
        },
        {
            # "incoming": True,  # omitted defaults to True
            "outgoing": False,
        },
        {
            "incoming": False,
            "outgoing": True,
        },
    ],
)
async def test_telegram_trigger_options(
    hass: HomeAssistant,
    calls: list[ServiceCall],
    knx: KNXTestKit,
    group_value_options: dict[str, bool],
    direction_options: dict[str, bool],
) -> None:
    """Test telegram trigger options."""
    await knx.setup_integration({})
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                # "catch_all" trigger
                {
                    "trigger": {
                        "platform": "knx.telegram",
                        **group_value_options,
                        **direction_options,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "catch_all": ("telegram - {{ trigger.destination }}"),
                        },
                    },
                },
            ]
        },
    )
    await knx.receive_write("0/0/1", 1)
    if group_value_options.get("group_value_write", True) and direction_options.get(
        "incoming", True
    ):
        assert len(calls) == 1
        assert calls.pop().data["catch_all"] == "telegram - 0/0/1"
    else:
        assert len(calls) == 0

    await knx.receive_response("0/0/1", 1)
    if group_value_options["group_value_response"] and direction_options.get(
        "incoming", True
    ):
        assert len(calls) == 1
        assert calls.pop().data["catch_all"] == "telegram - 0/0/1"
    else:
        assert len(calls) == 0

    await knx.receive_read("0/0/1")
    if group_value_options["group_value_read"] and direction_options.get(
        "incoming", True
    ):
        assert len(calls) == 1
        assert calls.pop().data["catch_all"] == "telegram - 0/0/1"
    else:
        assert len(calls) == 0

    await hass.services.async_call(
        "knx",
        "send",
        {"address": "0/0/1", "payload": True},
        blocking=True,
    )
    await knx.assert_write("0/0/1", True)
    if (
        group_value_options.get("group_value_write", True)
        and direction_options["outgoing"]
    ):
        assert len(calls) == 1
        assert calls.pop().data["catch_all"] == "telegram - 0/0/1"
    else:
        assert len(calls) == 0


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
