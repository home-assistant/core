"""Tests for Specialized Turbo diagnostics."""

from __future__ import annotations

from unittest.mock import MagicMock

from specialized_turbo import TelemetrySnapshot

from homeassistant.components.specialized_turbo.const import CONF_PIN, DOMAIN
from homeassistant.components.specialized_turbo.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from .conftest import MOCK_ADDRESS, MOCK_ADDRESS_FORMATTED

from tests.common import MockConfigEntry


async def test_diagnostics_structure(hass: HomeAssistant) -> None:
    """Test diagnostics output has the expected structure."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ADDRESS: MOCK_ADDRESS, CONF_PIN: 1234},
        unique_id=MOCK_ADDRESS_FORMATTED,
    )
    entry.add_to_hass(hass)

    snapshot = TelemetrySnapshot()
    snapshot.message_count = 42
    snapshot.battery.charge_pct = 80
    snapshot.battery.voltage_v = 36.5
    snapshot.motor.speed_kmh = 25.0
    snapshot.settings.assist_lev1_pct = 30

    mock_coordinator = MagicMock()
    mock_coordinator.snapshot = snapshot
    entry.runtime_data = mock_coordinator

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert "entry" in result
    assert "snapshot" in result
    assert result["snapshot"]["message_count"] == 42
    assert result["snapshot"]["battery"]["charge_pct"] == 80
    assert result["snapshot"]["motor"]["speed_kmh"] == 25.0
    assert result["snapshot"]["settings"]["assist_lev1_pct"] == 30


async def test_diagnostics_redacts_sensitive_data(hass: HomeAssistant) -> None:
    """Test that PIN and address are redacted in diagnostics output."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ADDRESS: MOCK_ADDRESS, CONF_PIN: 1234},
        unique_id=MOCK_ADDRESS_FORMATTED,
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_coordinator.snapshot = TelemetrySnapshot()
    entry.runtime_data = mock_coordinator

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["entry"]["data"][CONF_PIN] == "**REDACTED**"
    assert result["entry"]["data"][CONF_ADDRESS] == "**REDACTED**"


async def test_diagnostics_empty_snapshot(hass: HomeAssistant) -> None:
    """Test diagnostics with an empty snapshot."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ADDRESS: MOCK_ADDRESS},
        unique_id=MOCK_ADDRESS_FORMATTED,
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_coordinator.snapshot = TelemetrySnapshot()
    entry.runtime_data = mock_coordinator

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["snapshot"]["message_count"] == 0
