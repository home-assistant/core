"""Test OpenEVSE diagnostics."""

import asyncio
from datetime import datetime
from enum import Enum
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.openevse.const import DOMAIN
from homeassistant.components.openevse.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_charger: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test OpenEVSE diagnostics and redacted data."""
    entry = MockConfigEntry(
        title="openevse_mock_config",
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "my_username",
            CONF_PASSWORD: "my_password",
        },
        entry_id="FAKE_AUTH",
        unique_id="deadbeeffeed",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diagnostics == snapshot(exclude=props("created_at", "modified_at"))


async def test_entry_diagnostics_exceptions(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test OpenEVSE diagnostics handles exceptions and JSON coercion correctly."""

    class MockEnum(Enum):
        TEST = "test_value"

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Configure the mock_charger after setup to isolate side effects
    mock_charger.vehicle_eta = datetime(2000, 1, 1, 12, 0, 0)
    mock_charger.mode = MockEnum.TEST
    mock_charger.wifi_firmware = lambda: "callable_value"

    # Delete status to simulate attribute not present and trigger AttributeError
    delattr(mock_charger, "status")

    # Patch charging_voltage to raise ValueError
    with patch.object(
        type(mock_charger),
        "charging_voltage",
        PropertyMock(side_effect=ValueError("Connection error")),
        create=True,
    ):
        diagnostics = await get_diagnostics_for_config_entry(
            hass, hass_client, mock_config_entry
        )

    # status should be omitted because the attribute is not present
    assert "status" not in diagnostics["charger"]

    # charging_voltage should show the recorded error type only
    assert diagnostics["charger"]["charging_voltage"] == "Error: ValueError"

    # vehicle_eta should be coerced to ISO format string
    assert diagnostics["charger"]["vehicle_eta"] == "2000-01-01T12:00:00"

    # mode should be coerced to Enum raw value
    assert diagnostics["charger"]["mode"] == "test_value"

    # wifi_firmware should be omitted because it is callable
    assert "wifi_firmware" not in diagnostics["charger"]


async def test_entry_diagnostics_cancelled_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_charger: MagicMock,
) -> None:
    """Test OpenEVSE diagnostics handles asyncio.CancelledError correctly."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Raise CancelledError on status access using patch.object
    with (
        patch.object(
            type(mock_charger),
            "status",
            PropertyMock(side_effect=asyncio.CancelledError()),
            create=True,
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await async_get_config_entry_diagnostics(hass, mock_config_entry)
