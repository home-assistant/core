"""Test SmartThings diagnostics."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.smartthings.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry, load_json_object_fixture
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    devices: AsyncMock,
    mock_smartthings: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a device entry."""
    mock_smartthings.get_raw_devices.return_value = [
        load_json_object_fixture("devices/da_ac_rac_000001.json", DOMAIN)
    ]
    await setup_integration(hass, mock_config_entry)
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_device_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    devices: AsyncMock,
    mock_smartthings: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a device entry."""
    mock_smartthings.get_raw_device_status.return_value = load_json_object_fixture(
        "device_status/da_ac_rac_000001.json", DOMAIN
    )
    mock_smartthings.get_raw_device.return_value = load_json_object_fixture(
        "devices/da_ac_rac_000001.json", DOMAIN
    )["items"][0]
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, "96a5ef74-5832-a84b-f1f7-ca799957065d")}
    )

    mock_smartthings.get_raw_device_status.reset_mock()

    with patch("homeassistant.components.smartthings.diagnostics.EVENT_WAIT_TIME", 0.1):
        diag = await get_diagnostics_for_device(
            hass, hass_client, mock_config_entry, device
        )

    assert diag == snapshot(
        exclude=props("last_changed", "last_reported", "last_updated")
    )
    mock_smartthings.get_raw_device_status.assert_called_once_with(
        "96a5ef74-5832-a84b-f1f7-ca799957065d"
    )
