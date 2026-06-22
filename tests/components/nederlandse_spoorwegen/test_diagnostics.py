"""Tests for the diagnostics data provided by the Nederlandse Spoorwegen integration."""

from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.nederlandse_spoorwegen.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .const import SUBENTRY_ID_1

from tests.common import MockConfigEntry
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator


@pytest.mark.freeze_time("2025-09-15 14:30:00+00:00")
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_nsapi: AsyncMock,
) -> None:
    """Test config entry diagnostics."""
    mock_config_entry.add_to_hass(hass)
    await setup_integration(hass, mock_config_entry)

    # Trigger update for all coordinators before diagnostics
    for coordinator in mock_config_entry.runtime_data.values():
        await coordinator.async_refresh()

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )
    assert result == snapshot(exclude=props("created_at", "modified_at"))


@pytest.mark.freeze_time("2025-09-15 14:30:00+00:00")
async def test_device_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_nsapi: AsyncMock,
) -> None:
    """Test device diagnostics."""
    # Ensure integration is set up so device exists
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device(identifiers={(DOMAIN, SUBENTRY_ID_1)})
    assert device is not None

    # Trigger update for the coordinator before diagnostics
    coordinator = mock_config_entry.runtime_data[SUBENTRY_ID_1]
    await coordinator.async_refresh()

    result = await get_diagnostics_for_device(
        hass, hass_client, mock_config_entry, device
    )
    assert result == snapshot(exclude=props("created_at", "modified_at"))
