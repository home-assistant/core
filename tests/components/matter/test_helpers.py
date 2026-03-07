"""Test the Matter helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from matter_server.client.models.node import MatterNode
import pytest

from homeassistant.components.matter.const import DOMAIN
from homeassistant.components.matter.helpers import (
    get_device_id,
    get_node_binding_capabilities,
    get_node_from_device_entry,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .common import create_node_from_fixture, setup_integration_with_node_fixture

from tests.common import MockConfigEntry


@pytest.mark.parametrize("node_fixture", ["device_diagnostics"])
async def test_get_device_id(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test get_device_id."""
    device_id = get_device_id(matter_client.server_info, matter_node.endpoints[0])

    assert device_id == "00000000000004D2-0000000000000005-MatterNodeDevice"


async def test_get_node_from_device_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test get_node_from_device_entry."""
    other_domain = "other_domain"
    other_config_entry = MockConfigEntry(domain=other_domain)
    other_config_entry.add_to_hass(hass)
    other_device_entry = device_registry.async_get_or_create(
        config_entry_id=other_config_entry.entry_id,
        identifiers={(other_domain, "1234")},
    )
    node = await setup_integration_with_node_fixture(
        hass, "device_diagnostics", matter_client
    )
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    device_entry = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )[0]
    assert device_entry
    node_from_device_entry = get_node_from_device_entry(hass, device_entry)

    assert node_from_device_entry is node

    # test non-Matter device returns None
    assert get_node_from_device_entry(hass, other_device_entry) is None

    matter_client.server_info = None

    # test non-initialized server raises RuntimeError
    with pytest.raises(RuntimeError) as runtime_error:
        node_from_device_entry = get_node_from_device_entry(hass, device_entry)

    assert "Matter server information is not available" in str(runtime_error.value)


def test_get_node_binding_capabilities_light_switch() -> None:
    """Test binding capabilities for a light switch (source only)."""
    node = create_node_from_fixture("silabs_light_switch")
    capabilities = get_node_binding_capabilities(node)

    assert len(capabilities.source_endpoints) == 1
    assert capabilities.source_endpoints[0].endpoint_id == 1
    assert capabilities.source_endpoints[0].cluster_ids == {6, 768}
    assert len(capabilities.target_endpoints) == 0


def test_get_node_binding_capabilities_combo_device() -> None:
    """Test binding capabilities for a combo device (source and target)."""
    node = create_node_from_fixture("inovelli_vtm31")
    capabilities = get_node_binding_capabilities(node)

    assert len(capabilities.source_endpoints) == 1
    assert capabilities.source_endpoints[0].endpoint_id == 2
    assert capabilities.source_endpoints[0].cluster_ids == {6, 8}

    assert len(capabilities.target_endpoints) == 2
    assert capabilities.target_endpoints[0].endpoint_id == 1
    assert capabilities.target_endpoints[0].cluster_ids == {6, 8}
    assert capabilities.target_endpoints[1].endpoint_id == 6
    assert capabilities.target_endpoints[1].cluster_ids == {6, 8, 768}


def test_get_node_binding_capabilities_pure_target() -> None:
    """Test binding capabilities for a dimmable light (target only)."""
    node = create_node_from_fixture("mock_dimmable_light")
    capabilities = get_node_binding_capabilities(node)

    assert len(capabilities.source_endpoints) == 0
    assert len(capabilities.target_endpoints) == 1
    assert capabilities.target_endpoints[0].endpoint_id == 1
    assert capabilities.target_endpoints[0].cluster_ids == {6, 8}


def test_get_node_binding_capabilities_thermostat() -> None:
    """Test binding capabilities for a thermostat (target only)."""
    node = create_node_from_fixture("mock_thermostat")
    capabilities = get_node_binding_capabilities(node)

    assert len(capabilities.source_endpoints) == 0
    assert len(capabilities.target_endpoints) == 1
    assert capabilities.target_endpoints[0].endpoint_id == 1
    assert capabilities.target_endpoints[0].cluster_ids == {513}


def test_get_node_binding_capabilities_binding_without_client_clusters() -> None:
    """Test endpoint with Binding cluster but no bindable client clusters."""
    node = create_node_from_fixture("mock_occupancy_sensor")
    capabilities = get_node_binding_capabilities(node)

    # Endpoint 1 has Binding cluster but empty ClientList,
    # so it must not appear as a source endpoint
    assert len(capabilities.source_endpoints) == 0
    # Endpoint 1 ServerList contains bindable clusters, so it is a target
    assert len(capabilities.target_endpoints) == 1
    assert capabilities.target_endpoints[0].endpoint_id == 1
    assert capabilities.target_endpoints[0].cluster_ids == {
        6,
        8,
        257,
        258,
        512,
        513,
        768,
    }
