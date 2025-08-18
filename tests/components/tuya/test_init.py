"""Test Tuya initialization."""

from __future__ import annotations

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice

from homeassistant.components.tuya import ManagerCompat
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import initialize_entry

from tests.common import MockConfigEntry


@pytest.mark.parametrize("mock_device_code", ["ydkt_dolceclima_unsupported"])
async def test_unsupported_device(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test unsupported device."""

    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    # Device is registered
    assert (
        dr.async_entries_for_config_entry(device_registry, mock_config_entry.entry_id)
        == snapshot
    )
    # No entities registered
    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
