"""Tests for the KEBA P40 phase select."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("mock_client", "entity_registry_enabled_by_default")
async def test_select(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the phase select via snapshot."""
    with patch("homeassistant.components.keba_p40.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_select_sets_phases(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test selecting single-phase calls set_phases(1)."""
    with patch("homeassistant.components.keba_p40.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.garage_phase_mode", ATTR_OPTION: "single"},
        blocking=True,
    )
    mock_client.set_phases.assert_called_once_with("21900042", 1)
