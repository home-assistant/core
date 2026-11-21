"""Tests for the Daikin Onecta base entity."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.components.daikin_onecta.device import DaikinOnectaDevice
from homeassistant.components.daikin_onecta.entity import (
    _gateway_device_info,
    management_point_device_info,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo

from .platform_helpers import _async_setup_fixture, _load_gateway_devices


async def test_gateway_device_registry_uses_cloud_metadata(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Register gateway metadata from the config-entry cloud response."""
    await _async_setup_fixture(hass, config_entry, "dry")
    coordinator = config_entry.runtime_data
    gateway_id, device = next(iter(coordinator.data.items()))
    gateway_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, gateway_id), config_entry.entry_id
    )
    assert gateway_entry is not None
    model, serial_number, sw_version = device.gateway_metadata
    assert gateway_entry.name == device.name
    assert gateway_entry.manufacturer == "Daikin"
    assert gateway_entry.model_id == device.device.device_model
    assert gateway_entry.model == model
    assert gateway_entry.serial_number == serial_number
    assert gateway_entry.sw_version == sw_version

    climate_control_entities = [
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if any(
            f"{gateway_id}_{point.embedded_id}_" in entry.unique_id
            for point in device.device.management_points_by_type("climateControl")
        )
    ]
    assert climate_control_entities
    assert all(
        entry.device_id == gateway_entry.id for entry in climate_control_entities
    )

    indoor_unit = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"{gateway_id}_indoorUnit"), config_entry.entry_id
    )
    outdoor_unit = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"{gateway_id}_outdoorUnit"), config_entry.entry_id
    )
    assert indoor_unit is not None
    assert indoor_unit.name == "Indoor unit"
    assert outdoor_unit is not None
    assert outdoor_unit.name == "Outdoor unit"


async def test_main_zone_embedded_id_remains_a_climate_control(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Do not treat the main-zone embedded ID as a management-point type."""
    await _async_setup_fixture(hass, config_entry, "altherma")
    device = next(iter(config_entry.runtime_data.data.values()))
    point = device.device.management_points_by_type("climateControl")[0]
    assert point.embedded_id == "climateControlMainZone"

    device_info = management_point_device_info(device, point.embedded_id)

    assert device_info == _gateway_device_info(device)


def test_gateway_device_info_only_returns_its_identifier() -> None:
    """Let coordinator registration own gateway metadata updates."""
    device = MagicMock(id="gateway-id")

    assert _gateway_device_info(device) == DeviceInfo(
        identifiers={(DOMAIN, "gateway-id")}
    )


def test_management_point_device_info_requires_registered_gateway() -> None:
    """Do not attach a management point to the wrong gateway device."""
    device = DaikinOnectaDevice(_load_gateway_devices("dry")[0])
    device.ha_device_id = None
    point = device.device.management_points_by_type("indoorUnit")[0]

    with pytest.raises(RuntimeError, match="is not registered"):
        management_point_device_info(device, point.embedded_id)
