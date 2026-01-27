"""Tests for NRGkick device naming and fallback logic."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nrgkick.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import async_setup_integration

from tests.common import snapshot_platform

pytestmark = pytest.mark.usefixtures("entity_registry_enabled_by_default")


async def test_device_name_fallback(
    hass: HomeAssistant,
    mock_config_entry,
    mock_nrgkick_api,
    mock_info_data,
    mock_control_data,
    mock_values_data,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that device name is taken from the entry title."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, title="NRGkick")

    # Set empty device name in API response
    mock_info_data["general"]["device_name"] = ""
    mock_nrgkick_api.get_info.return_value = mock_info_data
    mock_nrgkick_api.get_control.return_value = mock_control_data
    mock_nrgkick_api.get_values.return_value = mock_values_data

    await async_setup_integration(hass, mock_config_entry, add_to_hass=False)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_info_data["general"]["serial_number"])}
    )
    assert device is not None
    assert device == snapshot(name="device")

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_device_name_custom(
    hass: HomeAssistant,
    mock_config_entry,
    mock_nrgkick_api,
    mock_info_data,
    mock_control_data,
    mock_values_data,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that custom device name is taken from the entry title."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, title="Garage Charger")

    # Set custom device name in API response
    mock_info_data["general"]["device_name"] = "Garage Charger"
    mock_nrgkick_api.get_info.return_value = mock_info_data
    mock_nrgkick_api.get_control.return_value = mock_control_data
    mock_nrgkick_api.get_values.return_value = mock_values_data

    await async_setup_integration(hass, mock_config_entry, add_to_hass=False)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_info_data["general"]["serial_number"])}
    )
    assert device is not None
    assert device == snapshot(name="device")

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
