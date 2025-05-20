"""Test the Z-Wave JS helpers module."""

from unittest.mock import patch

import pytest
import voluptuous as vol
from zwave_js_server.const import SecurityClass
from zwave_js_server.model.controller import ProvisioningEntry

from homeassistant.components.zwave_js.const import DOMAIN
from homeassistant.components.zwave_js.helpers import (
    async_get_node_status_sensor_entity_id,
    async_get_nodes_from_area_id,
    async_get_provisioning_entry_from_device_id,
    get_value_state_schema,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, device_registry as dr

from tests.common import MockConfigEntry

CONTROLLER_PATCH_PREFIX = "zwave_js_server.model.controller.Controller"


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return []


async def test_async_get_node_status_sensor_entity_id(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test async_get_node_status_sensor_entity_id for non zwave_js device."""
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "test")},
    )
    assert async_get_node_status_sensor_entity_id(hass, device.id) is None


async def test_async_get_nodes_from_area_id(
    hass: HomeAssistant, area_registry: ar.AreaRegistry
) -> None:
    """Test async_get_nodes_from_area_id."""
    area = area_registry.async_create("test")
    assert not async_get_nodes_from_area_id(hass, area.id)


async def test_get_value_state_schema_boolean_config_value(
    hass: HomeAssistant, client, aeon_smart_switch_6
) -> None:
    """Test get_value_state_schema for boolean config value."""
    schema_validator = get_value_state_schema(
        aeon_smart_switch_6.values["102-112-0-255"]
    )
    assert isinstance(schema_validator, vol.Coerce)
    assert schema_validator.type is bool


async def test_async_get_provisioning_entry_from_device_id(
    hass: HomeAssistant, client, device_registry: dr.DeviceRegistry, integration
) -> None:
    """Test async_get_provisioning_entry_from_device_id function."""
    device = device_registry.async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={(DOMAIN, "test-device")},
    )

    provisioning_entry = ProvisioningEntry.from_dict(
        {
            "dsk": "test",
            "securityClasses": [SecurityClass.S2_UNAUTHENTICATED],
            "device_id": device.id,
        }
    )

    with patch(
        f"{CONTROLLER_PATCH_PREFIX}.async_get_provisioning_entries",
        return_value=[provisioning_entry],
    ):
        result = await async_get_provisioning_entry_from_device_id(hass, device.id)
        assert result == provisioning_entry

    # Test invalid device
    with pytest.raises(ValueError, match="Device ID not-a-real-device is not valid"):
        await async_get_provisioning_entry_from_device_id(hass, "not-a-real-device")

    # Test device exists but is not from a zwave_js config entry
    non_zwave_config_entry = MockConfigEntry(domain="not_zwave_js")
    non_zwave_config_entry.add_to_hass(hass)
    non_zwave_device = device_registry.async_get_or_create(
        config_entry_id=non_zwave_config_entry.entry_id,
        identifiers={("not_zwave_js", "test-device")},
    )
    with pytest.raises(
        ValueError,
        match=f"Device {non_zwave_device.id} is not from an existing zwave_js config entry",
    ):
        await async_get_provisioning_entry_from_device_id(hass, non_zwave_device.id)

    # Test device exists but config entry is not loaded
    not_loaded_config_entry = MockConfigEntry(
        domain=DOMAIN, state=ConfigEntryState.NOT_LOADED
    )
    not_loaded_config_entry.add_to_hass(hass)
    not_loaded_device = device_registry.async_get_or_create(
        config_entry_id=not_loaded_config_entry.entry_id,
        identifiers={(DOMAIN, "not-loaded-device")},
    )
    with pytest.raises(
        ValueError, match=f"Device {not_loaded_device.id} config entry is not loaded"
    ):
        await async_get_provisioning_entry_from_device_id(hass, not_loaded_device.id)

    # Test no matching provisioning entry
    with patch(
        f"{CONTROLLER_PATCH_PREFIX}.async_get_provisioning_entries",
        return_value=[],
    ):
        result = await async_get_provisioning_entry_from_device_id(hass, device.id)
        assert result is None

    # Test multiple provisioning entries but only one matches
    other_provisioning_entry = ProvisioningEntry.from_dict(
        {
            "dsk": "other",
            "securityClasses": [SecurityClass.S2_UNAUTHENTICATED],
            "device_id": "other-id",
        }
    )
    with patch(
        f"{CONTROLLER_PATCH_PREFIX}.async_get_provisioning_entries",
        return_value=[other_provisioning_entry, provisioning_entry],
    ):
        result = await async_get_provisioning_entry_from_device_id(hass, device.id)
        assert result == provisioning_entry
