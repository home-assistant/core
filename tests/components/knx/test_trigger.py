"""Tests for KNX integration specific triggers."""

from collections.abc import Callable
import logging
from typing import Any

import pytest

from homeassistant.components import automation
from homeassistant.components.knx import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.trigger import async_get_all_descriptions
from homeassistant.setup import async_setup_component

from .conftest import KNXTestKit

TriggerStyle = Callable[[dict[str, Any]], dict[str, Any]]

# The telegram trigger accepts its options both at the top level - the config
# format from before the trigger was migrated to a trigger platform - and
# nested in `options`, which is what the automation editor writes.
TRIGGER_STYLES = [
    pytest.param(lambda options: options, id="top_level_options"),
    pytest.param(lambda options: {"options": options}, id="nested_options"),
]


async def test_telegram_trigger_description(
    hass: HomeAssistant,
    knx: KNXTestKit,
) -> None:
    """Test the telegram trigger is offered to the automation editor."""
    await knx.setup_integration()

    descriptions = await async_get_all_descriptions(hass)
    assert descriptions["knx.telegram"] is not None
    assert set(descriptions["knx.telegram"]["fields"]) == {
        "destination",
        "group_value_write",
        "group_value_response",
        "group_value_read",
        "incoming",
        "outgoing",
        "type",
    }


@pytest.mark.parametrize("trigger_style", TRIGGER_STYLES)
@pytest.mark.parametrize(
    "catch_all_options",
    [
        pytest.param({}, id="destination_omitted"),
        pytest.param({"destination": []}, id="destination_empty"),
    ],
)
async def test_telegram_trigger(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    knx: KNXTestKit,
    catch_all_options: dict[str, Any],
    trigger_style: TriggerStyle,
) -> None:
    """Test telegram triggers firing."""
    await knx.setup_integration()

    # "id" field added to action to test if `trigger_data` passed
    # correctly in `async_attach_trigger`
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                # "catch_all" trigger
                {
                    "trigger": {
                        "platform": "knx.telegram",
                        **trigger_style(catch_all_options),
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
                        **trigger_style(
                            {
                                # 2564 -> "1/2/4" in raw format
                                "destination": ["1/2/3", 2564],
                                "group_value_write": True,
                                "group_value_response": False,
                                "group_value_read": False,
                                "incoming": True,
                                "outgoing": True,
                            }
                        ),
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


@pytest.mark.parametrize("trigger_style", TRIGGER_STYLES)
@pytest.mark.parametrize(
    ("payload", "type_option", "expected_value", "expected_unit"),
    [
        ((0x4C,), {"type": "percent"}, 30, "%"),
        ((0x03,), {}, None, None),  # "type" omitted defaults to None
        ((0x0C, 0x1A), {"type": "temperature"}, 21.00, "°C"),
    ],
)
async def test_telegram_trigger_dpt_option(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    knx: KNXTestKit,
    payload: tuple[int, ...],
    type_option: dict[str, str],
    expected_value: int | None,
    expected_unit: str | None,
    trigger_style: TriggerStyle,
) -> None:
    """Test telegram trigger type option."""
    await knx.setup_integration()
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                # "catch_all" trigger
                {
                    "trigger": {
                        "platform": "knx.telegram",
                        **trigger_style(type_option),
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

    assert len(service_calls) == 1
    test_call = service_calls.pop()
    assert test_call.data["catch_all"] == "telegram - 0/0/1"
    assert test_call.data["trigger"]["value"] == expected_value
    assert test_call.data["trigger"]["unit"] == expected_unit

    await knx.receive_read("0/0/1")

    assert len(service_calls) == 1
    test_call = service_calls.pop()
    assert test_call.data["catch_all"] == "telegram - 0/0/1"
    assert test_call.data["trigger"]["value"] is None
    assert test_call.data["trigger"]["unit"] is None


@pytest.mark.parametrize("trigger_style", TRIGGER_STYLES)
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
    service_calls: list[ServiceCall],
    knx: KNXTestKit,
    group_value_options: dict[str, bool],
    direction_options: dict[str, bool],
    trigger_style: TriggerStyle,
) -> None:
    """Test telegram trigger options."""
    await knx.setup_integration()
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                # "catch_all" trigger
                {
                    "trigger": {
                        "platform": "knx.telegram",
                        **trigger_style({**group_value_options, **direction_options}),
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
        assert len(service_calls) == 1
        assert service_calls.pop().data["catch_all"] == "telegram - 0/0/1"
    else:
        assert len(service_calls) == 0

    await knx.receive_response("0/0/1", 1)
    if group_value_options["group_value_response"] and direction_options.get(
        "incoming", True
    ):
        assert len(service_calls) == 1
        assert service_calls.pop().data["catch_all"] == "telegram - 0/0/1"
    else:
        assert len(service_calls) == 0

    await knx.receive_read("0/0/1")
    if group_value_options["group_value_read"] and direction_options.get(
        "incoming", True
    ):
        assert len(service_calls) == 1
        assert service_calls.pop().data["catch_all"] == "telegram - 0/0/1"
    else:
        assert len(service_calls) == 0

    await hass.services.async_call(
        DOMAIN,
        "send",
        {"address": "0/0/1", "payload": True},
        blocking=True,
    )
    assert len(service_calls) == 1

    await knx.assert_write("0/0/1", True)
    if (
        group_value_options.get("group_value_write", True)
        and direction_options["outgoing"]
    ):
        assert len(service_calls) == 2
        assert service_calls.pop().data["catch_all"] == "telegram - 0/0/1"
    else:
        assert len(service_calls) == 1


async def test_remove_telegram_trigger(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    knx: KNXTestKit,
) -> None:
    """Test for removed callback when telegram trigger not used."""
    automation_name = "telegram_trigger_automation"
    await knx.setup_integration()

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


async def test_invalid_trigger(
    hass: HomeAssistant,
    knx: KNXTestKit,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid telegram trigger configuration."""
    await knx.setup_integration()
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
        assert (
            "Unnamed automation failed to setup triggers and has been disabled: "
            "not a valid option at 'invalid'. Got None" in caplog.records[0].message
        )
