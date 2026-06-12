"""Tests for the iTach remote platform."""

import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

from pyitach import ItachClient, ItachConnectionError
import pytest

from homeassistant.components.itach import remote
from homeassistant.components.itach.client import command_to_gc_timings
from homeassistant.components.itach.command import parse_pronto_command
from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
from homeassistant.const import (
    CONF_DEVICES,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PORT,
    DEVICE_DEFAULT_NAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

VALID_PRONTO = "0000 006D 0001 0000 0015 0016"
VALID_PRONTO_OFF = "0000 006D 0001 0000 0016 0017"

# Test helpers.


def _default_config(**overrides: Any) -> dict[str, Any]:
    """Return a default iTach YAML platform config."""
    config: dict[str, Any] = {
        CONF_HOST: "192.168.1.50",
        CONF_PORT: 4998,
        CONF_DEVICES: [
            {
                CONF_NAME: "TV",
                "connaddr": 1,
                "commands": [
                    {
                        CONF_NAME: "ON",
                        "data": VALID_PRONTO,
                    },
                ],
            }
        ],
    }
    config.update(overrides)
    return config


def _remote_config(**overrides: Any) -> dict[str, Any]:
    """Return a Home Assistant remote config for the iTach platform."""
    return {
        REMOTE_DOMAIN: [
            {
                "platform": "itach",
                **_default_config(**overrides),
            }
        ]
    }


async def _async_setup_itach_remote(
    hass: HomeAssistant,
    **overrides: Any,
) -> None:
    """Set up the iTach remote platform through Home Assistant."""
    assert await async_setup_component(
        hass,
        REMOTE_DOMAIN,
        _remote_config(**overrides),
    )
    await hass.async_block_till_done()


def _mock_itach_client() -> MagicMock:
    """Return a mocked pyitach client."""
    mock_client = MagicMock(spec=ItachClient)
    mock_client.async_connect = AsyncMock()
    mock_client.async_send_ir = AsyncMock()
    mock_client.close = AsyncMock()
    return mock_client


def _parsed_command(data: str = VALID_PRONTO) -> Any:
    """Return parsed test command data."""
    return parse_pronto_command(data)


def _expected_send_ir_call(
    module: int,
    connector: int,
    command_data: str,
    repeat: int,
) -> Any:
    """Return expected async_send_ir call."""
    command = parse_pronto_command(command_data)
    return call(
        module,
        connector,
        command.modulation,
        command_to_gc_timings(command),
        repeat=repeat,
    )


async def test_setup_platform_creates_entity(hass: HomeAssistant) -> None:
    """Test setup creates one remote entity from YAML config."""
    mock_client = _mock_itach_client()

    with patch(
        "homeassistant.components.itach.client.ItachClient",
        return_value=mock_client,
    ):
        await _async_setup_itach_remote(hass)

    state = hass.states.get("remote.tv")

    assert state is not None
    assert state.state == "off"


async def test_setup_platform_initializes_client(hass: HomeAssistant) -> None:
    """Test setup initializes the pyitach client with YAML values."""
    mock_client = _mock_itach_client()

    with patch(
        "homeassistant.components.itach.client.ItachClient",
        return_value=mock_client,
    ) as mock_client_class:
        await _async_setup_itach_remote(
            hass,
            **{CONF_MAC: "AA:BB:CC:DD:EE:FF"},
        )

    mock_client_class.assert_called_once_with(
        "192.168.1.50",
        4998,
        timeout=remote.CONNECT_TIMEOUT / 1000,
    )
    mock_client.async_connect.assert_awaited_once_with()


async def test_setup_platform_closes_client_on_home_assistant_stop(
    hass: HomeAssistant,
) -> None:
    """Test setup closes the iTach client on Home Assistant stop."""
    mock_client = _mock_itach_client()

    with patch(
        "homeassistant.components.itach.client.ItachClient",
        return_value=mock_client,
    ):
        await _async_setup_itach_remote(hass)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_client.close.assert_awaited_once_with()


async def test_setup_platform_connect_failure(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setup does not create an entity when iTach cannot connect."""
    mock_client = _mock_itach_client()
    mock_client.async_connect.side_effect = ItachConnectionError("cannot connect")

    caplog.set_level(logging.ERROR)

    with patch(
        "homeassistant.components.itach.client.ItachClient",
        return_value=mock_client,
    ):
        await _async_setup_itach_remote(hass)

    assert hass.states.get("remote.tv") is None
    mock_client.async_connect.assert_awaited_once_with()
    mock_client.close.assert_awaited_once_with()
    assert "Unable to find iTach" in caplog.text


async def test_setup_platform_rejects_invalid_command_data(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setup does not create an entity with invalid command data."""
    mock_client = _mock_itach_client()
    devices = [
        {
            CONF_NAME: "TV",
            "connaddr": 1,
            "commands": [
                {
                    CONF_NAME: "ON",
                    "data": "sendir-on",
                },
            ],
        }
    ]

    caplog.set_level(logging.ERROR)

    with patch(
        "homeassistant.components.itach.client.ItachClient",
        return_value=mock_client,
    ):
        await _async_setup_itach_remote(hass, **{CONF_DEVICES: devices})

    assert hass.states.get("remote.tv") is None
    mock_client.close.assert_awaited_once_with()
    assert "Invalid iTach command data" in caplog.text


async def test_turn_on_sends_on_command() -> None:
    """Test turn_on sends the ON command."""
    mock_client = _mock_itach_client()
    entity = remote.ITachIP2IRRemote(
        mock_client, "TV", 1, 2, 2, {"ON": _parsed_command()}
    )

    with patch.object(entity, "async_write_ha_state") as mock_write_state:
        await entity.async_turn_on()

    assert entity.is_on is True
    assert mock_client.async_send_ir.await_args == _expected_send_ir_call(
        1, 2, VALID_PRONTO, 2
    )
    mock_write_state.assert_called_once_with()


async def test_turn_off_sends_off_command() -> None:
    """Test turn_off sends the OFF command."""
    mock_client = _mock_itach_client()
    entity = remote.ITachIP2IRRemote(
        mock_client, "TV", 1, 2, 2, {"OFF": _parsed_command(VALID_PRONTO_OFF)}
    )

    with patch.object(entity, "async_write_ha_state") as mock_write_state:
        await entity.async_turn_off()

    assert entity.is_on is False
    assert mock_client.async_send_ir.await_args == _expected_send_ir_call(
        1, 2, VALID_PRONTO_OFF, 2
    )
    mock_write_state.assert_called_once_with()


async def test_send_command_sends_each_command() -> None:
    """Test send_command sends each command."""
    mock_client = _mock_itach_client()
    entity = remote.ITachIP2IRRemote(
        mock_client,
        "TV",
        1,
        2,
        2,
        {
            "VOLUME_UP": _parsed_command(),
            "VOLUME_DOWN": _parsed_command(VALID_PRONTO_OFF),
        },
    )

    await entity.async_send_command(["VOLUME_UP", "VOLUME_DOWN"])

    assert mock_client.async_send_ir.await_args_list == [
        _expected_send_ir_call(1, 2, VALID_PRONTO, 2),
        _expected_send_ir_call(1, 2, VALID_PRONTO_OFF, 2),
    ]


async def test_send_command_applies_num_repeats_to_ir_count() -> None:
    """Test send_command multiplies ir_count by num_repeats."""
    mock_client = _mock_itach_client()
    entity = remote.ITachIP2IRRemote(
        mock_client, "TV", 1, 2, 2, {"VOLUME_UP": _parsed_command()}
    )

    await entity.async_send_command(["VOLUME_UP"], num_repeats=3)

    assert mock_client.async_send_ir.await_args == _expected_send_ir_call(
        1, 2, VALID_PRONTO, 6
    )


async def test_send_command_raises_for_unknown_command() -> None:
    """Test send_command raises for an unknown command."""
    mock_client = _mock_itach_client()
    entity = remote.ITachIP2IRRemote(
        mock_client, "TV", 1, 2, 2, {"VOLUME_UP": _parsed_command()}
    )

    with pytest.raises(
        HomeAssistantError, match="Command VOLUME_DOWN is not configured"
    ):
        await entity.async_send_command(["VOLUME_DOWN"])

    mock_client.async_send_ir.assert_not_awaited()


async def test_setup_platform_uses_default_values(hass: HomeAssistant) -> None:
    """Test setup uses default values for optional YAML fields."""
    mock_client = _mock_itach_client()
    devices = [
        {
            "connaddr": 2,
            "commands": [
                {
                    CONF_NAME: "ON",
                    "data": VALID_PRONTO,
                },
            ],
        }
    ]

    with patch(
        "homeassistant.components.itach.client.ItachClient",
        return_value=mock_client,
    ) as mock_client_class:
        await _async_setup_itach_remote(hass, **{CONF_DEVICES: devices})

    states = hass.states.async_all(REMOTE_DOMAIN)

    mock_client_class.assert_called_once_with(
        "192.168.1.50",
        4998,
        timeout=remote.CONNECT_TIMEOUT / 1000,
    )
    assert len(states) == 1
    assert states[0].name == DEVICE_DEFAULT_NAME


def test_commands_from_config_uses_empty_string_placeholder_for_empty_command_name() -> (
    None
):
    """Test empty command names are stored as placeholders."""
    commands = remote._commands_from_config(
        [
            {
                CONF_NAME: "",
                "data": VALID_PRONTO,
            }
        ]
    )

    assert list(commands) == [remote.EMPTY_COMMAND_PLACEHOLDER]
