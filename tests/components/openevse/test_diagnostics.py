"""Test OpenEVSE diagnostics."""

from datetime import datetime
from enum import Enum
from unittest.mock import MagicMock, PropertyMock

import pytest

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test OpenEVSE diagnostics."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert diagnostics["config_entry"]["data"] == {
        "host": "192.168.1.100",
    }
    assert diagnostics["charger"]["status"] == "Charging"
    assert diagnostics["charger"]["charging_voltage"] == 240
    assert diagnostics["charger"]["charging_current"] == 32000.0


async def test_entry_diagnostics_redact(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_charger: MagicMock,
) -> None:
    """Test OpenEVSE diagnostics with auth data redacted."""
    entry = MockConfigEntry(
        title="openevse_mock_config",
        domain="openevse",
        data={
            "host": "192.168.1.100",
            "username": "my_username",
            "password": "my_password",
        },
        entry_id="FAKE_AUTH",
        unique_id="deadbeeffeed",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diagnostics["config_entry"]["data"] == {
        "host": "192.168.1.100",
        "username": "**REDACTED**",
        "password": "**REDACTED**",
    }


async def test_entry_diagnostics_exceptions(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test OpenEVSE diagnostics handles exceptions and JSON coercion correctly."""

    class MockEnum(Enum):
        TEST = "test_value"

    # Set up one property to raise AttributeError (should be skipped)
    monkeypatch.setattr(
        type(mock_charger),
        "status",
        PropertyMock(side_effect=AttributeError),
        raising=False,
    )

    # Set up another property to raise a different Exception (should record the error)
    monkeypatch.setattr(
        type(mock_charger),
        "charging_voltage",
        PropertyMock(side_effect=ValueError("Connection error")),
        raising=False,
    )

    # Set up datetime property to verify JSON coercion
    monkeypatch.setattr(
        type(mock_charger),
        "vehicle_eta",
        PropertyMock(return_value=datetime(2000, 1, 1, 12, 0, 0)),
        raising=False,
    )

    # Set up Enum property to verify JSON coercion
    monkeypatch.setattr(
        type(mock_charger),
        "mode",
        PropertyMock(return_value=MockEnum.TEST),
        raising=False,
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    # status should be omitted due to AttributeError
    assert "status" not in diagnostics["charger"]

    # charging_voltage should show the recorded error
    assert (
        diagnostics["charger"]["charging_voltage"]
        == "Error: ValueError: Connection error"
    )

    # vehicle_eta should be coerced to ISO format string
    assert diagnostics["charger"]["vehicle_eta"] == "2000-01-01T12:00:00"

    # mode should be coerced to Enum raw value
    assert diagnostics["charger"]["mode"] == "test_value"
