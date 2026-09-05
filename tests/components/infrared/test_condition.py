"""Tests for the Infrared integration conditions."""

from typing import Any

from infrared_protocols.commands.nec import NECCommand
import pytest

from homeassistant.components import automation
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.condition import async_get_all_descriptions
from homeassistant.setup import async_setup_component

from .common import (
    RECEIVER_ENTITY_ID,
    MockInfraredReceiverEntity,
    captured_code,
    received_signal,
)

POWER = NECCommand(address=0x04FB, command=0xF7)
VOLUME_UP = NECCommand(address=0x04FB, command=0xF6)


async def _setup_automation(hass: HomeAssistant, *commands: str) -> None:
    """Set up an automation that only acts on the given command names."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "infrared",
                    "target": {"entity_id": RECEIVER_ENTITY_ID},
                    "options": {
                        "commands": [
                            {"name": "Power", "code": captured_code(POWER)},
                            {"name": "Volume up", "code": captured_code(VOLUME_UP)},
                        ]
                    },
                },
                "conditions": {
                    "condition": "infrared",
                    "options": {"command": list(commands)},
                },
                "actions": {
                    "action": "test.automation",
                    "data_template": {"command": "{{ trigger.command }}"},
                },
            }
        },
    )
    await hass.async_block_till_done()


@pytest.mark.usefixtures("init_infrared")
async def test_condition_description(hass: HomeAssistant) -> None:
    """Test the condition is offered to the automation editor."""
    descriptions = await async_get_all_descriptions(hass)

    assert descriptions["infrared"]["fields"]["command"] == {
        "required": True,
        "selector": {"infrared_command_name": {}},
    }


@pytest.mark.parametrize(
    ("command", "expected_calls"),
    [
        pytest.param(POWER, 1, id="named_command"),
        pytest.param(VOLUME_UP, 0, id="other_command_of_the_trigger"),
    ],
)
async def test_condition_matches_the_command_that_triggered(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    command: NECCommand,
    expected_calls: int,
) -> None:
    """Test the action only runs for the command names of the condition."""
    await _setup_automation(hass, "Power")

    mock_infrared_receiver_entity._handle_received_signal(received_signal(command))
    await hass.async_block_till_done()

    assert len(service_calls) == expected_calls


async def test_condition_matches_any_of_its_commands(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test naming several commands passes for each of them."""
    await _setup_automation(hass, "Power", "Volume up")

    mock_infrared_receiver_entity._handle_received_signal(received_signal(VOLUME_UP))
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["command"] == "Volume up"


async def test_condition_without_an_infrared_trigger(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test the condition does not pass when no infrared command started the run."""
    await _setup_automation(hass, "Power")

    await hass.services.async_call(
        automation.DOMAIN,
        "trigger",
        {"entity_id": "automation.automation_0", "skip_condition": False},
        blocking=True,
    )

    # Only the automation.trigger call itself was recorded.
    assert len(service_calls) == 1


@pytest.mark.parametrize(
    ("options", "error"),
    [
        pytest.param(
            {"command": []},
            "length of value must be at least 1 at 'options.command'",
            id="no_commands",
        ),
        pytest.param(
            {},
            "required key not provided at 'options.command'",
            id="command_missing",
        ),
        pytest.param(
            {"command": [""]},
            "length of value must be at least 1 at 'options.command[0]'",
            id="empty_name",
        ),
    ],
)
@pytest.mark.usefixtures("mock_infrared_receiver_entity")
async def test_invalid_config(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    options: dict[str, Any],
    error: str,
) -> None:
    """Test an automation with an unusable condition config is not set up."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {"trigger": "event", "event_type": "test_event"},
                "conditions": {"condition": "infrared", "options": options},
                "actions": {"action": "test.automation"},
            }
        },
    )

    assert error in caplog.text
