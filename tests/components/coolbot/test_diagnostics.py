"""Diagnostics: useful content, credentials never included."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.coolbot.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import TEST_EMAIL, TEST_PASSWORD

from tests.common import MockConfigEntry


async def test_diagnostics_redact_identity_and_credentials(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Diagnostics carry device state but never credentials or identifiers."""
    assert await setup_integration(hass, mock_config_entry)

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    flat = str(diagnostics)
    assert TEST_PASSWORD not in flat
    assert TEST_EMAIL not in flat
    assert "AA:BB:CC:DD:EE:FF" not in flat

    assert diagnostics["device_count"] == 1
    (device,) = diagnostics["devices"]
    assert device["room_temp_f"] == 38.5
    assert device["considered_fresh"] is True
    assert isinstance(device["data_age_seconds"], float)
