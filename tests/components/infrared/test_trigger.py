"""Tests for the Infrared integration triggers."""

from typing import Any

from infrared_protocols.commands.nec import NECCommand
import pytest

from homeassistant.components import automation
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.trigger import async_get_all_descriptions
from homeassistant.setup import async_setup_component

from .common import (
    RECEIVER_ENTITY_ID,
    MockInfraredReceiverEntity,
    captured_code as _code,
    received_signal as _signal,
)

POWER = NECCommand(address=0x04FB, command=0xF7)
VOLUME_UP = NECCommand(address=0x04FB, command=0xF6)
OTHER_REMOTE = NECCommand(address=0x0102, command=0xF7)


async def _setup_automation(hass: HomeAssistant, *commands: NECCommand) -> None:
    """Set up an automation triggering on the given commands."""
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
                            {"name": f"Command {index}", "code": _code(command)}
                            for index, command in enumerate(commands)
                        ]
                    },
                },
                "actions": {
                    "action": "test.automation",
                    "data_template": {
                        "command": "{{ trigger.command }}",
                        "entity_id": "{{ trigger.entity_id }}",
                    },
                },
            }
        },
    )
    await hass.async_block_till_done()


@pytest.mark.usefixtures("init_infrared")
async def test_trigger_description(hass: HomeAssistant) -> None:
    """Test the trigger is offered to the automation editor."""
    descriptions = await async_get_all_descriptions(hass)

    assert descriptions["infrared"]["target"] == {
        "entity": [{"domain": ["infrared"], "device_class": ["receiver"]}]
    }
    assert descriptions["infrared"]["fields"]["commands"] == {
        "required": True,
        "selector": {"infrared_command": {}},
        "context": {"filter_target": "target"},
    }


@pytest.mark.parametrize(
    ("repeat_count", "expected_command"),
    [
        pytest.param(0, "Command 0", id="single_frame"),
        pytest.param(3, "Command 0", id="button_held"),
    ],
)
async def test_trigger_fires_for_captured_command(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    repeat_count: int,
    expected_command: str,
) -> None:
    """Test the trigger fires with the name given to the captured command."""
    await _setup_automation(hass, POWER, VOLUME_UP)

    mock_infrared_receiver_entity._handle_received_signal(
        _signal(POWER, repeat_count=repeat_count)
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data == {
        "command": expected_command,
        "entity_id": RECEIVER_ENTITY_ID,
    }


async def test_trigger_fires_for_second_command(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test each captured command triggers under its own name."""
    await _setup_automation(hass, POWER, VOLUME_UP)

    mock_infrared_receiver_entity._handle_received_signal(_signal(VOLUME_UP))
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["command"] == "Command 1"


@pytest.mark.parametrize(
    "command",
    [
        pytest.param(OTHER_REMOTE, id="other_remote"),
        pytest.param(NECCommand(address=0x04FB, command=0xF5), id="other_button"),
    ],
)
async def test_trigger_ignores_other_commands(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    command: NECCommand,
) -> None:
    """Test a signal that is not a captured command does not trigger."""
    await _setup_automation(hass, POWER, VOLUME_UP)

    mock_infrared_receiver_entity._handle_received_signal(_signal(command))
    await hass.async_block_till_done()

    assert len(service_calls) == 0


async def test_trigger_ignores_other_receiver(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test a command received by an untargeted receiver does not trigger."""
    from homeassistant.components.infrared import DATA_COMPONENT  # noqa: PLC0415

    other_receiver = MockInfraredReceiverEntity("other_ir_receiver", "Other receiver")
    await hass.data[DATA_COMPONENT].async_add_entities([other_receiver])
    await _setup_automation(hass, POWER)

    other_receiver._handle_received_signal(_signal(POWER))
    await hass.async_block_till_done()

    assert len(service_calls) == 0


@pytest.mark.usefixtures("mock_infrared_receiver_entity")
async def test_trigger_without_target(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a trigger that does not select a receiver is refused."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "infrared",
                    "target": {},
                    "options": {"commands": [{"name": "Power", "code": _code(POWER)}]},
                },
                "actions": {"action": "test.automation"},
            }
        },
    )

    assert "No target defined" in caplog.text


@pytest.mark.parametrize(
    ("options", "error"),
    [
        pytest.param(
            {"commands": []},
            "length of value must be at least 1 at 'options.commands'",
            id="no_commands",
        ),
        pytest.param(
            {},
            "required key not provided at 'options.commands'",
            id="commands_missing",
        ),
        pytest.param(
            {"commands": [{"name": "Power", "code": "not pronto"}]},
            "Invalid infrared code",
            id="invalid_code",
        ),
        pytest.param(
            {"commands": [{"name": "", "code": _code(POWER)}]},
            "length of value must be at least 1",
            id="empty_name",
        ),
        pytest.param(
            {"commands": [{"code": _code(POWER)}]},
            "required key not provided at 'options.commands[0].name'",
            id="name_missing",
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
    """Test an automation with an unusable trigger config is not set up."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "triggers": {
                    "trigger": "infrared",
                    "target": {"entity_id": RECEIVER_ENTITY_ID},
                    "options": options,
                },
                "actions": {"action": "test.automation"},
            }
        },
    )

    assert "failed to setup triggers and has been disabled" in caplog.text
    assert error in caplog.text
