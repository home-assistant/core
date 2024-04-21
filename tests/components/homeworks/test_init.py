"""Tests for the Lutron Homeworks Series 4 and 8 integration."""

from unittest.mock import ANY, MagicMock

from pyhomeworks.pyhomeworks import HW_BUTTON_PRESSED, HW_BUTTON_RELEASED
import pytest

from homeassistant.components.homeworks import EVENT_BUTTON_PRESS, EVENT_BUTTON_RELEASE
from homeassistant.components.homeworks.const import CONF_DIMMERS, CONF_KEYPADS, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_capture_events


async def test_import(
    hass: HomeAssistant,
    mock_homeworks: MagicMock,
) -> None:
    """Test the Homeworks YAML import."""
    await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_HOST: "192.168.0.1",
                CONF_PORT: 1234,
                CONF_DIMMERS: [],
                CONF_KEYPADS: [],
            }
        },
    )
    await hass.async_block_till_done()

    assert len(hass.config_entries.flow.async_progress()) == 1
    assert hass.config_entries.flow.async_progress()[0]["context"]["source"] == "import"


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homeworks: MagicMock,
) -> None:
    """Test the Homeworks configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_homeworks.assert_called_once_with("192.168.0.1", 1234, ANY)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homeworks: MagicMock,
) -> None:
    """Test the Homeworks configuration entry not ready."""
    mock_homeworks.side_effect = ConnectionError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_homeworks.assert_called_once()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_keypad_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homeworks: MagicMock,
) -> None:
    """Test Homeworks keypad events."""
    release_events = async_capture_events(hass, EVENT_BUTTON_RELEASE)
    press_events = async_capture_events(hass, EVENT_BUTTON_PRESS)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_homeworks.assert_called_once_with("192.168.0.1", 1234, ANY)
    hw_callback = mock_homeworks.mock_calls[0][1][2]

    hw_callback(HW_BUTTON_PRESSED, ["[02:08:02:01]", 1])
    await hass.async_block_till_done()
    assert len(press_events) == 1
    assert len(release_events) == 0
    assert press_events[0].data == {
        "id": "foyer_keypad",
        "name": "Foyer Keypad",
        "button": 1,
    }
    assert press_events[0].event_type == "homeworks_button_press"

    hw_callback(HW_BUTTON_RELEASED, ["[02:08:02:01]", 1])
    await hass.async_block_till_done()
    assert len(press_events) == 1
    assert len(release_events) == 1
    assert release_events[0].data == {
        "id": "foyer_keypad",
        "name": "Foyer Keypad",
        "button": 1,
    }
    assert release_events[0].event_type == "homeworks_button_release"

    hw_callback("unsupported", ["[02:08:02:01]", 1])
    await hass.async_block_till_done()
    assert len(press_events) == 1
    assert len(release_events) == 1


async def test_send_command(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homeworks: MagicMock,
) -> None:
    """Test the send command service."""
    mock_controller = MagicMock()
    mock_homeworks.return_value = mock_controller

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_controller._send.reset_mock()
    await hass.services.async_call(
        DOMAIN,
        "send_command",
        {"controller_id": "main_controller", "command": "KBP, [02:08:02:01], 1"},
        blocking=True,
    )
    assert len(mock_controller._send.mock_calls) == 1
    assert mock_controller._send.mock_calls[0][1] == ("KBP, [02:08:02:01], 1",)

    mock_controller._send.reset_mock()
    await hass.services.async_call(
        DOMAIN,
        "send_command",
        {
            "controller_id": "main_controller",
            "command": [
                "KBP, [02:08:02:01], 1",
                "KBH, [02:08:02:01], 1",
                "KBR, [02:08:02:01], 1",
            ],
        },
        blocking=True,
    )
    assert len(mock_controller._send.mock_calls) == 3
    assert mock_controller._send.mock_calls[0][1] == ("KBP, [02:08:02:01], 1",)
    assert mock_controller._send.mock_calls[1][1] == ("KBH, [02:08:02:01], 1",)
    assert mock_controller._send.mock_calls[2][1] == ("KBR, [02:08:02:01], 1",)

    mock_controller._send.reset_mock()
    await hass.services.async_call(
        DOMAIN,
        "send_command",
        {
            "controller_id": "main_controller",
            "command": [
                "KBP, [02:08:02:01], 1",
                "delay 50",
                "KBH, [02:08:02:01], 1",
                "dElAy 100",
                "KBR, [02:08:02:01], 1",
            ],
        },
        blocking=True,
    )
    assert len(mock_controller._send.mock_calls) == 3
    assert mock_controller._send.mock_calls[0][1] == ("KBP, [02:08:02:01], 1",)
    assert mock_controller._send.mock_calls[1][1] == ("KBH, [02:08:02:01], 1",)
    assert mock_controller._send.mock_calls[2][1] == ("KBR, [02:08:02:01], 1",)

    mock_controller._send.reset_mock()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "send_command",
            {"controller_id": "unknown_controller", "command": "KBP, [02:08:02:01], 1"},
            blocking=True,
        )
    assert len(mock_controller._send.mock_calls) == 0
