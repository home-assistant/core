"""Test the Z-Wave JS helpers module."""

from unittest.mock import MagicMock, patch

import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry
from zwave_js_server.const import SecurityClass
from zwave_js_server.model.controller import ProvisioningEntry
from zwave_js_server.model.endpoint import Endpoint
from zwave_js_server.model.node import EndpointGroup, Node
from zwave_js_server.model.value import Value as ZwaveValue

from homeassistant.components.zwave_js.const import DOMAIN
from homeassistant.components.zwave_js.helpers import (
    async_get_node_status_sensor_entity_id,
    async_get_nodes_from_area_id,
    async_get_provisioning_entry_from_device_id,
    endpoint_device_for_late_value,
    endpoint_devices,
    format_home_id_for_display,
    get_device_id,
    get_endpoint_device_id,
    get_home_and_node_id_from_device_entry,
    get_value_state_schema,
)
from homeassistant.components.zwave_js.models import PlatformZwaveDiscoveryInfo
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, device_registry as dr

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


async def test_async_get_nodes_from_area_id_includes_child_device(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    climate_heatit_z_trm3: Node,
    integration: MockConfigEntry,
) -> None:
    """Test async_get_nodes_from_area_id resolves an endpoint child device to its node."""
    node = climate_heatit_z_trm3
    area = area_registry.async_create("sensor area")
    node_device = device_registry.async_get_device_by_identifier(
        get_device_id(client.driver, node), integration.entry_id
    )
    assert node_device
    child_device = device_registry.async_get_or_create_child(
        config_entry_id=integration.entry_id,
        identifiers={get_endpoint_device_id(client.driver, node, node.endpoints[2])},
        parent_device_id=node_device.id,
    )
    device_registry.async_update_child_device(child_device.id, area_id=area.id)

    # An area that contains only a child device still resolves to its node.
    assert async_get_nodes_from_area_id(hass, area.id) == {node}


async def test_get_value_state_schema_boolean_config_value(
    hass: HomeAssistant, client, aeon_smart_switch_6
) -> None:
    """Test get_value_state_schema for boolean config value."""
    schema_validator = get_value_state_schema(
        aeon_smart_switch_6.values["102-112-0-255"]
    )
    assert isinstance(schema_validator, probatio.Coerce)
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


async def test_get_endpoint_device_id(
    client: MagicMock, vision_security_zl7432: Node, aeotec_zwa046: Node
) -> None:
    """Test get_endpoint_device_id for endpoint and group child devices."""
    driver = client.driver
    home_id = driver.controller.home_id

    # A per-endpoint child device identifier includes the endpoint index.
    node = vision_security_zl7432
    assert get_endpoint_device_id(driver, node, node.endpoints[2]) == (
        DOMAIN,
        f"{home_id}-{node.node_id}-2",
    )

    # An endpoint-group child device identifier includes the group id.
    group_node = aeotec_zwa046
    assert get_endpoint_device_id(
        driver, group_node, group_node.endpoint_groups[1]
    ) == (DOMAIN, f"{home_id}-{group_node.node_id}-g1")


def _make_disc_info(node: Node, value: ZwaveValue) -> PlatformZwaveDiscoveryInfo:
    """Build a minimal discovery info for a node value."""
    return PlatformZwaveDiscoveryInfo(
        node=node,
        primary_value=value,
        assumed_state=False,
        platform=Platform.SENSOR,
        additional_value_ids_to_watch=set(),
    )


def _find_value(
    node: Node,
    command_class: int,
    endpoint: int,
    property_: str,
    property_key: int | None = None,
) -> ZwaveValue:
    """Find a node value by command class, endpoint, property and property key."""
    return next(
        value
        for value in node.values.values()
        if value.command_class == command_class
        and value.endpoint == endpoint
        and value.property_ == property_
        and value.property_key == property_key
    )


async def test_endpoint_devices_groups(client: MagicMock, aeotec_zwa046: Node) -> None:
    """Test endpoint_devices groups endpoints by their non-main endpoint group."""
    node = aeotec_zwa046
    # Meter values on an endpoint in the non-main "Clamp 1" group and on an endpoint
    # in the main-device "Total" group.
    clamp1_value = _find_value(node, 50, 1, "value", 65537)
    total_value = _find_value(node, 50, 7, "value", 66049)

    result = endpoint_devices(
        node, [_make_disc_info(node, clamp1_value), _make_disc_info(node, total_value)]
    )

    # Endpoints in a non-main group are placed on one child device for that group.
    clamp1 = result[clamp1_value.value_id]
    assert isinstance(clamp1, EndpointGroup)
    assert clamp1.label == "Clamp 1"
    # Endpoints in a main-device group stay on the node device.
    assert total_value.value_id not in result


async def test_endpoint_devices_labels(
    client: MagicMock, climate_heatit_z_trm3: Node, vision_security_zl7432: Node
) -> None:
    """Test endpoint_devices splits labeled, colliding endpoints without groups."""
    node = climate_heatit_z_trm3
    air2 = _find_value(node, 49, 2, "Air temperature")
    air3 = _find_value(node, 49, 3, "Air temperature")
    air4 = _find_value(node, 49, 4, "Air temperature")
    # The labeled "Thermostat" endpoint carries a setpoint that does not collide.
    setpoint = _find_value(node, 67, 1, "setpoint", 1)

    result = endpoint_devices(
        node,
        [_make_disc_info(node, value) for value in (air2, air3, air4, setpoint)],
    )

    # Labeled endpoints whose air temperature collides get a per-endpoint child device.
    assert isinstance(result[air2.value_id], Endpoint)
    assert result[air2.value_id].endpoint_label == "Room Sensor"
    assert result[air3.value_id].endpoint_label == "External Sensor"
    assert result[air4.value_id].endpoint_label == "Floor Sensor"
    # A labeled endpoint with no colliding value stays on the node device.
    assert setpoint.value_id not in result

    # ZL7432: two endpoints collide but have no labels and no groups, so no split.
    zl7432 = vision_security_zl7432
    zl_ep1 = _find_value(zl7432, 37, 1, "currentValue")
    zl_ep2 = _find_value(zl7432, 37, 2, "currentValue")
    assert (
        endpoint_devices(
            zl7432, [_make_disc_info(zl7432, zl_ep1), _make_disc_info(zl7432, zl_ep2)]
        )
        == {}
    )


async def test_endpoint_device_for_late_value(
    client: MagicMock, climate_heatit_z_trm3: Node, aeotec_zwa046: Node
) -> None:
    """Test endpoint_device_for_late_value resolves placement for values added late."""
    node = climate_heatit_z_trm3
    air2 = _find_value(node, 49, 2, "Air temperature")
    air3 = _find_value(node, 49, 3, "Air temperature")
    air4 = _find_value(node, 49, 4, "Air temperature")
    setpoint = _find_value(node, 67, 1, "setpoint", 1)
    config = _find_value(node, 112, 0, 2)
    placements = endpoint_devices(
        node, [_make_disc_info(node, value) for value in (air2, air3, air4)]
    )

    # A value on an endpoint that already has a child device is placed on that child.
    result = endpoint_device_for_late_value(node, placements, air3)
    assert isinstance(result, Endpoint)
    assert result.index == 3

    # A value on a non-child endpoint, and a root (endpoint 0) value, stay on the node.
    assert endpoint_device_for_late_value(node, placements, setpoint) is None
    assert endpoint_device_for_late_value(node, placements, config) is None

    # In the groups case placement is derived from the node's static group config, so a
    # value on a non-main group endpoint is placed on that group even with no prior
    # placements cached, while a main-device group endpoint stays on the node.
    group_node = aeotec_zwa046
    clamp1_value = _find_value(group_node, 50, 1, "value", 65537)
    total_value = _find_value(group_node, 50, 7, "value", 66049)
    clamp1 = endpoint_device_for_late_value(group_node, {}, clamp1_value)
    assert isinstance(clamp1, EndpointGroup)
    assert clamp1.label == "Clamp 1"
    assert endpoint_device_for_late_value(group_node, {}, total_value) is None


async def test_get_home_and_node_id_from_device_entry(
    hass: HomeAssistant,
    client: MagicMock,
    device_registry: dr.DeviceRegistry,
    integration: MockConfigEntry,
) -> None:
    """Test get_home_and_node_id_from_device_entry with node and endpoint identifiers."""
    driver = client.driver
    home_id = driver.controller.home_id

    # 2-segment node identifier resolves to (home_id, node_id).
    node_device = device_registry.async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={(DOMAIN, f"{home_id}-7")},
    )
    result = get_home_and_node_id_from_device_entry(node_device)
    assert result == (str(home_id), 7)

    # 3-segment endpoint identifier resolves to the same (home_id, node_id); the
    # endpoint segment is ignored so services targeting a child device resolve to the
    # node.
    endpoint_device = device_registry.async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={(DOMAIN, f"{home_id}-7-2")},
    )
    assert get_home_and_node_id_from_device_entry(endpoint_device) == (str(home_id), 7)

    # A provision_ identifier resolves to None.
    provision_device = device_registry.async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={(DOMAIN, f"provision_{home_id}-7")},
    )
    assert get_home_and_node_id_from_device_entry(provision_device) is None


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
