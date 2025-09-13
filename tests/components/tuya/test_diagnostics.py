"""Test Tuya diagnostics platform."""

from __future__ import annotations

import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.tuya.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import initialize_entry

from tests.common import MockConfigEntry
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator


@pytest.mark.parametrize("mock_device_code", ["rqbj_4iqe2hsfyd86kwwc"])
async def test_entry_diagnostics(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result == snapshot(
        exclude=props("last_changed", "last_reported", "last_updated")
    )


@pytest.mark.parametrize("mock_device_code", ["rqbj_4iqe2hsfyd86kwwc"])
async def test_device_diagnostics(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device diagnostics."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    device = device_registry.async_get_device(identifiers={(DOMAIN, mock_device.id)})
    assert device, repr(device_registry.devices)

    result = await get_diagnostics_for_device(
        hass, hass_client, mock_config_entry, device
    )
    assert result == snapshot(
        exclude=props("last_changed", "last_reported", "last_updated")
    )
