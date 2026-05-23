"""Tests for ISY994 services."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from homeassistant.components.isy994.const import DOMAIN
from homeassistant.components.isy994.services import (
    SERVICE_SEND_PROGRAM_COMMAND,
    async_setup_services,
    valid_isy_commands,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

# ---------------------------------------------------------------------------
# valid_isy_commands
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("DON", "DON", id="uppercase_valid"),
        pytest.param("don", "DON", id="lowercase_coerced"),
        pytest.param("ST", "ST", id="status_valid"),
    ],
)
def test_valid_isy_commands_valid(value: str, expected: str) -> None:
    """Valid ISY commands are returned in uppercase."""
    assert valid_isy_commands(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("NOTACOMMAND", id="unknown_string"),
        pytest.param("", id="empty_string"),
    ],
)
def test_valid_isy_commands_invalid(value: str) -> None:
    """Invalid ISY commands raise vol.Invalid."""
    with pytest.raises(vol.Invalid):
        valid_isy_commands(value)


# ---------------------------------------------------------------------------
# async_setup_services: service registration
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ignore_missing_translations", ["component.isy994.services."])
async def test_async_setup_services_registers_all(hass: HomeAssistant) -> None:
    """async_setup_services registers all expected services."""
    expected = {
        "send_program_command",
        "send_raw_node_command",
        "send_node_command",
        "get_zwave_parameter",
        "set_zwave_parameter",
        "rename_node",
    }
    async_setup_services(hass)
    for service in expected:
        assert hass.services.has_service(DOMAIN, service), f"Missing service: {service}"


# ---------------------------------------------------------------------------
# send_program_command service handler
# ---------------------------------------------------------------------------


def _make_config_entry(hass: HomeAssistant, isy_name: str = "Test ISY") -> MagicMock:
    """Register a loaded mock config entry whose runtime_data exposes an ISY."""
    entry = MockConfigEntry(domain=DOMAIN, entry_id=f"entry_{isy_name}")
    entry.add_to_hass(hass)
    isy = MagicMock()
    isy.conf = {"name": isy_name}
    isy.programs = MagicMock()
    isy.programs.get_by_id.return_value = None
    isy.programs.get_by_name.return_value = None
    runtime_data = MagicMock()
    runtime_data.root = isy
    entry.runtime_data = runtime_data
    return entry


@pytest.mark.parametrize("ignore_missing_translations", ["component.isy994.services."])
async def test_send_program_command_by_name(hass: HomeAssistant) -> None:
    """send_program_command calls the right program method when found by name."""
    entry = _make_config_entry(hass)
    isy = entry.runtime_data.root

    program = MagicMock()
    program.run = AsyncMock()
    isy.programs.get_by_name.return_value = program

    async_setup_services(hass)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_loaded_entries",
        return_value=[entry],
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_PROGRAM_COMMAND,
            {"name": "My Program", "command": "run"},
            blocking=True,
        )

    program.run.assert_awaited_once()


@pytest.mark.parametrize("ignore_missing_translations", ["component.isy994.services."])
async def test_send_program_command_by_address(hass: HomeAssistant) -> None:
    """send_program_command calls the right program method when found by address."""
    entry = _make_config_entry(hass)
    isy = entry.runtime_data.root

    program = MagicMock()
    program.enable = AsyncMock()
    isy.programs.get_by_id.return_value = program

    async_setup_services(hass)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_loaded_entries",
        return_value=[entry],
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_PROGRAM_COMMAND,
            {"address": "0001", "command": "enable"},
            blocking=True,
        )

    program.enable.assert_awaited_once()


@pytest.mark.parametrize("ignore_missing_translations", ["component.isy994.services."])
async def test_send_program_command_isy_name_filter(hass: HomeAssistant) -> None:
    """isy_name filter skips entries whose ISY name does not match."""
    entry_match = _make_config_entry(hass, "TargetISY")
    entry_skip = _make_config_entry(hass, "OtherISY")

    program = MagicMock()
    program.run = AsyncMock()
    entry_match.runtime_data.root.programs.get_by_name.return_value = program
    entry_skip.runtime_data.root.programs.get_by_name.return_value = program

    async_setup_services(hass)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_loaded_entries",
        return_value=[entry_skip, entry_match],
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_PROGRAM_COMMAND,
            {"name": "My Program", "command": "run", "isy": "TargetISY"},
            blocking=True,
        )

    program.run.assert_awaited_once()


@pytest.mark.parametrize("ignore_missing_translations", ["component.isy994.services."])
async def test_send_program_command_not_found_logs_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """send_program_command logs an error when no program is found."""
    entry = _make_config_entry(hass)

    async_setup_services(hass)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_loaded_entries",
        return_value=[entry],
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_PROGRAM_COMMAND,
            {"name": "Nonexistent Program", "command": "run"},
            blocking=True,
        )

    assert "Could not send program command" in caplog.text
