"""Test the Zinvolt initialization."""

from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion
from zinvolt.exceptions import ZinvoltAuthenticationError

from homeassistant.components.zinvolt.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_zinvolt_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Zinvolt device."""
    await setup_integration(hass, mock_config_entry)
    devices = device_registry._devices
    for device in devices.values():
        assert device == snapshot(name=list(device.identifiers)[0][1])


async def test_device_via_device_links(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_zinvolt_client: AsyncMock,
) -> None:
    """Test that a unit sub-device links to its main battery device via via_device_id."""
    await setup_integration(hass, mock_config_entry)

    battery_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "ZVG011025120088"), mock_config_entry.entry_id
    )
    assert battery_device is not None

    unit_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "BAT002"), mock_config_entry.entry_id
    )
    assert unit_device is not None
    assert unit_device.via_device_id == battery_device.id


@pytest.mark.parametrize(
    "method", ["get_batteries", "get_units", "get_battery_status", "get_battery_unit"]
)
async def test_setup_authentication_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zinvolt_client: AsyncMock,
    method: str,
) -> None:
    """Test an authentication error during setup starts a reauth flow."""
    getattr(mock_zinvolt_client, method).side_effect = ZinvoltAuthenticationError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id
