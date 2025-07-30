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
    caplog: pytest.LogCaptureFixture,
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

    # Information log entry added
    assert (
        "Device DOLCECLIMA 10 HP WIFI (mock_device_id) has been ignored"
        " as it does not provide any standard instructions (status, status_range"
        " and function are all empty) - see "
        "https://github.com/tuya/tuya-device-sharing-sdk/issues/11" in caplog.text
    )
