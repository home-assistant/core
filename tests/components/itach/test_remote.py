"""Tests for the iTach remote platform."""

import logging
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from homeassistant.components.itach import remote
from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
from homeassistant.const import (
    CONF_DEVICES,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PORT,
    DEVICE_DEFAULT_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

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
                        "data": "sendir-on",
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


async def test_setup_platform_creates_entity(hass: HomeAssistant) -> None:
    """Test setup creates one remote entity from YAML config."""
    mock_itach = MagicMock()
    mock_itach.ready.return_value = True

    with patch(
        "homeassistant.components.itach.remote.pyitachip2ir.ITachIP2IR",
        return_value=mock_itach,
    ):
        await _async_setup_itach_remote(hass)

    state = hass.states.get("remote.tv")

    assert state is not None
    assert state.state == "off"


async def test_setup_platform_initializes_library(hass: HomeAssistant) -> None:
    """Test setup initializes the pyitachip2ir client with YAML values."""
    mock_itach = MagicMock()
    mock_itach.ready.return_value = True

    with patch(
        "homeassistant.components.itach.remote.pyitachip2ir.ITachIP2IR",
        return_value=mock_itach,
    ) as mock_itach_class:
        await _async_setup_itach_remote(
            hass,
            **{CONF_MAC: "AA:BB:CC:DD:EE:FF"},
        )

    mock_itach_class.assert_called_once_with(
        "AA:BB:CC:DD:EE:FF",
        "192.168.1.50",
        4998,
    )


async def test_setup_platform_ready_failure(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setup does not create an entity when iTach is not ready."""
    mock_itach = MagicMock()
    mock_itach.ready.return_value = False

    caplog.set_level(logging.ERROR)

    with patch(
        "homeassistant.components.itach.remote.pyitachip2ir.ITachIP2IR",
        return_value=mock_itach,
    ):
        await _async_setup_itach_remote(hass)

    assert hass.states.get("remote.tv") is None
    mock_itach.ready.assert_called_once_with(remote.CONNECT_TIMEOUT)
    mock_itach.addDevice.assert_not_called()
    assert "Unable to find iTach" in caplog.text


async def test_setup_platform_adds_device_with_command_table(
    hass: HomeAssistant,
) -> None:
    """Test setup adds a device with the expected command table."""
    mock_itach = MagicMock()
    mock_itach.ready.return_value = True
    devices = [
        {
            CONF_NAME: "TV",
            "modaddr": 1,
            "connaddr": 2,
            "commands": [
                {
                    CONF_NAME: "ON",
                    "data": "sendir-on",
                },
                {
                    CONF_NAME: "OFF",
                    "data": "sendir-off",
                },
            ],
        }
    ]

    with patch(
        "homeassistant.components.itach.remote.pyitachip2ir.ITachIP2IR",
        return_value=mock_itach,
    ):
        await _async_setup_itach_remote(hass, **{CONF_DEVICES: devices})

    mock_itach.addDevice.assert_called_once_with(
        "TV",
        1,
        2,
        "ON\nsendir-on\nOFF\nsendir-off\n",
    )


def test_turn_on_sends_on_command() -> None:
    """Test turn_on sends the ON command."""
    mock_itach = MagicMock()
    entity = remote.ITachIP2IRRemote(mock_itach, "TV", 2)

    with patch.object(entity, "schedule_update_ha_state") as mock_schedule_update:
        entity.turn_on()

    assert entity.is_on is True
    mock_itach.send.assert_called_once_with("TV", "ON", 2)
    mock_schedule_update.assert_called_once_with()


def test_turn_off_sends_off_command() -> None:
    """Test turn_off sends the OFF command."""
    mock_itach = MagicMock()
    entity = remote.ITachIP2IRRemote(mock_itach, "TV", 2)

    with patch.object(entity, "schedule_update_ha_state") as mock_schedule_update:
        entity.turn_off()

    assert entity.is_on is False
    mock_itach.send.assert_called_once_with("TV", "OFF", 2)
    mock_schedule_update.assert_called_once_with()


def test_send_command_sends_each_command() -> None:
    """Test send_command sends each command."""
    mock_itach = MagicMock()
    entity = remote.ITachIP2IRRemote(mock_itach, "TV", 2)

    entity.send_command(["VOLUME_UP", "VOLUME_DOWN"])

    assert mock_itach.send.call_args_list == [
        call("TV", "VOLUME_UP", 2),
        call("TV", "VOLUME_DOWN", 2),
    ]


def test_send_command_applies_num_repeats_to_ir_count() -> None:
    """Test send_command multiplies ir_count by num_repeats."""
    mock_itach = MagicMock()
    entity = remote.ITachIP2IRRemote(mock_itach, "TV", 2)

    entity.send_command(["VOLUME_UP"], num_repeats=3)

    mock_itach.send.assert_called_once_with("TV", "VOLUME_UP", 6)


def test_update_calls_library_update() -> None:
    """Test update calls the pyitachip2ir update method."""
    mock_itach = MagicMock()
    entity = remote.ITachIP2IRRemote(mock_itach, "TV", 2)

    entity.update()

    mock_itach.update.assert_called_once_with()


async def test_setup_platform_uses_default_values(hass: HomeAssistant) -> None:
    """Test setup uses default values for optional YAML fields."""
    mock_itach = MagicMock()
    mock_itach.ready.return_value = True
    devices = [
        {
            "connaddr": 2,
            "commands": [
                {
                    CONF_NAME: "ON",
                    "data": "sendir-on",
                },
            ],
        }
    ]

    with patch(
        "homeassistant.components.itach.remote.pyitachip2ir.ITachIP2IR",
        return_value=mock_itach,
    ) as mock_itach_class:
        await _async_setup_itach_remote(hass, **{CONF_DEVICES: devices})

    states = hass.states.async_all(REMOTE_DOMAIN)

    mock_itach_class.assert_called_once_with(None, "192.168.1.50", 4998)
    mock_itach.addDevice.assert_called_once_with(
        None,
        1,
        2,
        "ON\nsendir-on\n",
    )
    assert len(states) == 1
    assert states[0].name == DEVICE_DEFAULT_NAME


async def test_setup_platform_uses_empty_string_placeholders_for_empty_commands(
    hass: HomeAssistant,
) -> None:
    """Test setup converts empty command names and data to placeholders."""
    mock_itach = MagicMock()
    mock_itach.ready.return_value = True
    devices = [
        {
            CONF_NAME: "TV",
            "connaddr": 1,
            "commands": [
                {
                    CONF_NAME: "",
                    "data": "",
                },
                {
                    CONF_NAME: "   ",
                    "data": "   ",
                },
            ],
        }
    ]

    with patch(
        "homeassistant.components.itach.remote.pyitachip2ir.ITachIP2IR",
        return_value=mock_itach,
    ):
        await _async_setup_itach_remote(hass, **{CONF_DEVICES: devices})

    mock_itach.addDevice.assert_called_once_with(
        "TV",
        1,
        1,
        '""\n""\n""\n""\n',
    )
