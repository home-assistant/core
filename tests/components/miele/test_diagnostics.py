"""Tests for the diagnostics data provided by the miele integration."""

from unittest.mock import MagicMock

from pymiele import MieleDevices, completed_warnings
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import paths

from homeassistant.components.miele.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry

from . import get_data_callback, setup_integration

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
    mock_miele_client.get_programs.assert_not_awaited()


@pytest.mark.parametrize("load_device_file", ["coffee_system.json"])
async def test_device_diagnostics_retains_unknown_program(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: DeviceRegistry,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_fixture: MieleDevices,
) -> None:
    """Test diagnostics retain unknown programs after the program finishes."""
    device_id = "DummyAppliance_CoffeeSystem"
    warning = "Missing CoffeeSystemProgramId code: 99999 - defaulting to Unknown"
    try:
        await setup_integration(hass, mock_config_entry)
        device_entry = device_registry.async_get_device_by_identifier(
            (DOMAIN, device_id), mock_config_entry.entry_id
        )
        assert device_entry is not None

        program_id = device_fixture[device_id]["state"]["ProgramID"]
        program_id["value_raw"] = 99999
        program_id["value_localized"] = "Mystery drink"
        data_callback = get_data_callback(mock_miele_client)
        await data_callback(device_fixture)

        program_id["value_raw"] = 0
        program_id["value_localized"] = ""
        await data_callback(device_fixture)

        result = await get_diagnostics_for_device(
            hass, hass_client, mock_config_entry, device_entry
        )

        assert result["miele_data"]["unknown_program_ids"] == [
            {"value_raw": 99999, "value_localized": "Mystery drink"}
        ]
        mock_miele_client.get_programs.assert_not_awaited()
    finally:
        completed_warnings.discard(warning)
