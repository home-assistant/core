"""Tests for the diagnostics data provided by the miele integration."""

from unittest.mock import MagicMock

from aiohttp import ClientConnectionError, ClientResponseError
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import paths

from homeassistant.components.miele.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry

from . import setup_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator

TEST_DEVICE = "Dummy_Appliance_1"


async def test_diagnostics_config_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for config entry."""

    await setup_integration(hass, mock_config_entry)
    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result == snapshot(
        exclude=paths(
            "config_entry_data.token.expires_at",
            "miele_test.entry_id",
        )
    )
    mock_miele_client.get_programs.assert_not_awaited()


async def test_diagnostics_device(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: DeviceRegistry,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for device."""

    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_DEVICE), mock_config_entry.entry_id
    )
    assert device_entry is not None

    result = await get_diagnostics_for_device(
        hass, hass_client, mock_config_entry, device_entry
    )
    assert result == snapshot(
        exclude=paths(
            "data.token.expires_at",
            "miele_test.entry_id",
        )
    )
    mock_miele_client.get_programs.assert_awaited_once_with(TEST_DEVICE)


@pytest.mark.parametrize(
    ("programs_error", "expected_programs_diagnostics"),
    [
        pytest.param(
            ClientResponseError(MagicMock(), (), status=404),
            {"error": "ClientResponseError", "status": 404},
            id="unsupported",
        ),
        pytest.param(
            ClientConnectionError(),
            {"error": "ClientConnectionError"},
            id="offline",
        ),
        pytest.param(TimeoutError(), {"error": "TimeoutError"}, id="timeout"),
    ],
)
async def test_device_diagnostics_programs_unavailable(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: DeviceRegistry,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    programs_error: Exception,
    expected_programs_diagnostics: dict[str, int | str],
) -> None:
    """Test device diagnostics remain available when programs are unavailable."""
    await setup_integration(hass, mock_config_entry)
    mock_miele_client.get_programs.side_effect = programs_error
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_DEVICE), mock_config_entry.entry_id
    )
    assert device_entry is not None

    result = await get_diagnostics_for_device(
        hass, hass_client, mock_config_entry, device_entry
    )

    assert result["miele_data"]["programs"] == expected_programs_diagnostics
    assert "devices" in result["miele_data"]
