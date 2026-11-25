"""Test the Matter helpers."""

from typing import Any
from unittest.mock import MagicMock

from matter_server.client.models.node import MatterNode
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.matter.const import DOMAIN
from homeassistant.components.matter.helpers import (
    endpoint_requires_child_device,
    get_child_device_owner,
    get_device_id,
    get_node_from_device_entry,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .common import (
    TAPO_STRIP_NUMBER_TAG_ATTRIBUTES,
    create_node_from_fixture,
    setup_integration_with_node_fixture,
)


@pytest.mark.parametrize(
    ("node_fixture", "endpoint_id", "expected"),
    [
        # Root endpoint always maps to the node (parent) device.
        ("eve_energy_20ecn4101", 0, False),
        # Each socket of the dual-socket plug (same device type) splits off,
        # named from its vendor label.
        ("eve_energy_20ecn4101", 1, True),
        ("eve_energy_20ecn4101", 2, True),
        ("tp_link_smart_outdoor_plug", 1, True),
        # Each relay named from its Common Number semantic tag splits off.
        ("lifx_switch_115", 41, True),
        # Sockets without semantic tags or vendor labels naming them don't split.
        ("tapo_smart_wi_fi_power_strip", 1, False),
        ("dewenwils_3_zone_transformer", 1, False),
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


EVE_ENERGY_COMPOSED_PART_ATTRIBUTES = {
    "0/29/3": [1, 2, 3],
    "1/29/3": [3],
    "3/29/0": [{"0": 770, "1": 1}],
    "3/29/1": [29, 1026],
    "3/29/2": [],
    "3/29/3": [],
    "3/1026/0": 2100,
}


@pytest.mark.parametrize(
    ("node_fixture", "attributes", "endpoint_id", "expected_owner_id"),
    [
        pytest.param(
            "tapo_smart_wi_fi_power_strip",
            TAPO_STRIP_NUMBER_TAG_ATTRIBUTES,
            7,
            1,
            id="set_single_first",
        ),
        pytest.param(
            "tapo_smart_wi_fi_power_strip",
            TAPO_STRIP_NUMBER_TAG_ATTRIBUTES,
            12,
            6,
            id="set_single_last",
        ),
        pytest.param(
            "tapo_smart_wi_fi_power_strip",
            TAPO_STRIP_NUMBER_TAG_ATTRIBUTES,
            1,
            1,
            id="split_outlet",
        ),
        pytest.param(
            "tapo_smart_wi_fi_power_strip",
            TAPO_STRIP_NUMBER_TAG_ATTRIBUTES,
            0,
            None,
            id="root",
        ),
        pytest.param(
            "tapo_smart_wi_fi_plug_265", None, 2, None, id="set_outlet_not_split"
        ),
        pytest.param("silabs_dishwasher", None, 2, None, id="set_several_endpoints"),
        pytest.param("inovelli_vtm30", None, 7, None, id="node_topology"),
        pytest.param("aqara_thermostat_w500", None, 0, None, id="node_topology_root"),
        pytest.param(
            "eve_energy_20ecn4101",
            EVE_ENERGY_COMPOSED_PART_ATTRIBUTES,
            3,
            1,
            id="composed_part_of_split_endpoint",
        ),
    ],
)
def test_get_child_device_owner(
    node_fixture: str,
    attributes: dict[str, Any] | None,
    endpoint_id: int,
    expected_owner_id: int | None,
) -> None:
    """Test which endpoint's child device holds an endpoint's entities."""
    node = create_node_from_fixture(node_fixture, attributes)

    owner = get_child_device_owner(node.endpoints[endpoint_id])

    assert owner is node.endpoints.get(expected_owner_id)


@pytest.mark.parametrize("node_fixture", ["device_diagnostics"])
async def test_get_device_id(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test get_device_id."""
    device_id = get_device_id(matter_client.server_info, matter_node.endpoints[0])

    assert device_id == "00000000000004D2-00000000000003ED-MatterNodeDevice"


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
