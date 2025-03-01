"""Tests for the SmartThings component init module."""

from unittest.mock import AsyncMock

from pysmartthings import DeviceResponse, DeviceStatus
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.smartthings.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry, load_fixture


async def test_devices(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    device_id = devices.get_devices.return_value[0].device_id

    device = device_registry.async_get_device({(DOMAIN, device_id)})

    assert device is not None
    assert device == snapshot


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_removing_stale_devices(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test removing stale devices."""
    mock_config_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "aaa-bbb-ccc")},
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not device_registry.async_get_device({(DOMAIN, "aaa-bbb-ccc")})


async def test_hub_via_device(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_smartthings: AsyncMock,
) -> None:
    """Test hub with child devices."""
    mock_smartthings.get_devices.return_value = DeviceResponse.from_json(
        load_fixture("devices/hub.json", DOMAIN)
    ).items
    mock_smartthings.get_device_status.side_effect = [
        DeviceStatus.from_json(
            load_fixture(f"device_status/{fixture}.json", DOMAIN)
        ).components
        for fixture in ("hub", "multipurpose_sensor")
    ]
    await setup_integration(hass, mock_config_entry)

    hub_device = device_registry.async_get_device(
        {(DOMAIN, "074fa784-8be8-4c70-8e22-6f5ed6f81b7e")}
    )
    assert hub_device == snapshot
    assert (
        device_registry.async_get_device(
            {(DOMAIN, "374ba6fa-5a08-4ea2-969c-1fa43d86e21f")}
        ).via_device_id
        == hub_device.id
    )
