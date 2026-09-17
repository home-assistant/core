"""Test the Matter helpers."""

from unittest.mock import MagicMock

from matter_server.client.models.node import MatterNode
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.matter.const import DOMAIN
from homeassistant.components.matter.helpers import (
    endpoint_requires_child_device,
    get_device_id,
    get_node_from_device_entry,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .common import create_node_from_fixture, setup_integration_with_node_fixture


@pytest.mark.parametrize(
    ("node_fixture", "endpoint_id", "expected"),
    [
        # Root endpoint always maps to the node (parent) device.
        ("eve_energy_20ecn4101", 0, False),
        # Each socket of the dual-socket plug (same device type) splits off.
        ("eve_energy_20ecn4101", 1, True),
        ("eve_energy_20ecn4101", 2, True),
        # Endpoints sharing a primary attribute but of different device types are
        # the same physical unit, so they are not split.
        ("inovelli_vtm31", 1, False),
        # Generic Switch (button) endpoints are not split.
        ("haojai_switch", 1, False),
        # A nested composed endpoint collapses onto its compose parent device.
        ("silabs_refrigerator", 2, False),
        # A bridge's endpoints are never split into child devices; their bridged
        # devices are already separate HA devices.
        ("mock_composed_bridge", 3, False),
    ],
)
def test_endpoint_requires_child_device(
    node_fixture: str, endpoint_id: int, expected: bool
) -> None:
    """Test which endpoints are represented as their own child device."""
    node = create_node_from_fixture(node_fixture)

    assert endpoint_requires_child_device(node.endpoints[endpoint_id]) is expected


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
