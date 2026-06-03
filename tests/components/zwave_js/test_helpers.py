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
    format_home_id_for_display,
    get_device_id,
    get_node_id_and_endpoint_from_device_entry,
    get_value_state_schema,
    value_requires_endpoint_device,
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
        match=(
            f"Device {non_zwave_device.id} is not from an"
            " existing zwave_js config entry"
        ),
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


async def test_get_device_id_with_endpoint(client, vision_security_zl7432) -> None:
    """Test get_device_id with an endpoint argument."""
    driver = client.driver
    node = vision_security_zl7432
    home_id = driver.controller.home_id

    node_device_id = get_device_id(driver, node)
    assert node_device_id == (DOMAIN, f"{home_id}-{node.node_id}")

    # Endpoint 0 and None map to the node device.
    assert get_device_id(driver, node, 0) == node_device_id
    assert get_device_id(driver, node, None) == node_device_id

    # A non-root endpoint maps to a sub-device identifier.
    assert get_device_id(driver, node, 2) == (
        DOMAIN,
        f"{home_id}-{node.node_id}-2",
    )


async def test_value_requires_endpoint_device(client, vision_security_zl7432) -> None:
    """Test value_requires_endpoint_device collision detection."""
    node = vision_security_zl7432

    # The root endpoint value always stays on the node device.
    root_value = node.values[f"{node.node_id}-114-0-manufacturerId"]
    assert not value_requires_endpoint_device(node, root_value)

    # Both non-root endpoints collide with each other and get their own device.
    endpoint_1_value = node.values[f"{node.node_id}-37-1-currentValue"]
    assert value_requires_endpoint_device(node, endpoint_1_value)
    endpoint_2_value = node.values[f"{node.node_id}-37-2-currentValue"]
    assert value_requires_endpoint_device(node, endpoint_2_value)


async def test_get_node_id_and_endpoint_from_device_entry(
    hass: HomeAssistant, client, device_registry: dr.DeviceRegistry, integration
) -> None:
    """Test get_node_id_and_endpoint_from_device_entry."""
    driver = client.driver
    home_id = driver.controller.home_id

    node_device = device_registry.async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={(DOMAIN, f"{home_id}-7")},
    )
    assert get_node_id_and_endpoint_from_device_entry(node_device) is None

    # The hardware signature identifier is not an endpoint sub-device.
    ext_device = device_registry.async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={(DOMAIN, f"{home_id}-7-265:8215:5911")},
    )
    assert get_node_id_and_endpoint_from_device_entry(ext_device) is None

    endpoint_device = device_registry.async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={(DOMAIN, f"{home_id}-7-2")},
    )
    assert get_node_id_and_endpoint_from_device_entry(endpoint_device) == (7, 2)


def test_format_home_id_for_display() -> None:
    """Test format_home_id_for_display."""
    # Test with standard home ID
    assert format_home_id_for_display(3245146787) == "0xc16d02a3"

    # Test with zero
    assert format_home_id_for_display(0) == "0x00000000"

    # Test with max 32-bit value
    assert format_home_id_for_display(4294967295) == "0xffffffff"

    # Test with None
    assert format_home_id_for_display(None) == "Unknown"
