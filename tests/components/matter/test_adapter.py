"""Test the adapter."""

from __future__ import annotations

from unittest.mock import MagicMock

from matter_server.client.models.node import MatterNode
from matter_server.common.helpers.util import dataclass_from_dict
from matter_server.common.models import EventType, MatterNodeData
import pytest

from homeassistant.components.matter.adapter import get_clean_name
from homeassistant.components.matter.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .common import load_and_parse_node_fixture, setup_integration_with_node_fixture


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
@pytest.mark.parametrize(
    ("node_fixture", "name"),
    [
        ("onoff-light", "Mock OnOff Light"),
        ("onoff-light-alt-name", "Mock OnOff Light"),
        ("onoff-light-no-name", "Mock Light"),
    ],
)
async def test_device_registry_single_node_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
    node_fixture: str,
    name: str,
) -> None:
    """Test bridge devices are set up correctly with via_device."""
    await setup_integration_with_node_fixture(
        hass,
        node_fixture,
        matter_client,
    )

    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    # test serial id present as additional identifier
    assert (DOMAIN, "serial_12345678") in entry.identifiers

    assert entry.name == name
    assert entry.manufacturer == "Nabu Casa"
    assert entry.model == "Mock Light"
    assert entry.hw_version == "v1.0"
    assert entry.sw_version == "v1.0"
    assert entry.serial_number == "12345678"


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_device_registry_single_node_device_alt(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test additional device with different attribute values."""
    await setup_integration_with_node_fixture(
        hass,
        "on-off-plugin-unit",
        matter_client,
    )

    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    # test name is derived from productName (because nodeLabel is absent)
    assert entry.name == "Mock OnOffPluginUnit (powerplug/switch)"

    # test serial id NOT present as additional identifier
    assert (DOMAIN, "serial_TEST_SN") not in entry.identifiers
    assert entry.serial_number is None


@pytest.mark.skip("Waiting for a new test fixture")
async def test_device_registry_bridge(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test bridge devices are set up correctly with via_device."""
    await setup_integration_with_node_fixture(
        hass,
        "fake-bridge-two-light",
        matter_client,
    )

    # Validate bridge
    bridge_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "mock-hub-id")}
    )
    assert bridge_entry is not None

    assert bridge_entry.name == "My Mock Bridge"
    assert bridge_entry.manufacturer == "Mock Vendor"
    assert bridge_entry.model == "Mock Bridge"
    assert bridge_entry.hw_version == "TEST_VERSION"
    assert bridge_entry.sw_version == "123.4.5"

    # Device 1
    device1_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "mock-id-kitchen-ceiling")}
    )
    assert device1_entry is not None

    assert device1_entry.via_device_id == bridge_entry.id
    assert device1_entry.name == "Kitchen Ceiling"
    assert device1_entry.manufacturer == "Mock Vendor"
    assert device1_entry.model == "Mock Light"
    assert device1_entry.hw_version is None
    assert device1_entry.sw_version == "67.8.9"

    # Device 2
    device2_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "mock-id-living-room-ceiling")}
    )
    assert device2_entry is not None

    assert device2_entry.via_device_id == bridge_entry.id
    assert device2_entry.name == "Living Room Ceiling"
    assert device2_entry.manufacturer == "Mock Vendor"
    assert device2_entry.model == "Mock Light"
    assert device2_entry.hw_version is None
    assert device2_entry.sw_version == "1.49.1"


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_node_added_subscription(
    hass: HomeAssistant,
    matter_client: MagicMock,
    integration: MagicMock,
) -> None:
    """Test subscription to new devices work."""
    assert matter_client.subscribe_events.call_count == 5
    assert (
        matter_client.subscribe_events.call_args.kwargs["event_filter"]
        == EventType.NODE_UPDATED
    )

    node_added_callback = matter_client.subscribe_events.call_args.kwargs["callback"]
    node_data = load_and_parse_node_fixture("onoff-light")
    node = MatterNode(
        dataclass_from_dict(
            MatterNodeData,
            node_data,
        )
    )

    entity_state = hass.states.get("light.mock_onoff_light")
    assert not entity_state

    node_added_callback(EventType.NODE_ADDED, node)
    await hass.async_block_till_done()

    entity_state = hass.states.get("light.mock_onoff_light")
    assert entity_state


async def test_device_registry_single_node_composed_device(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Test that a composed device within a standalone node only creates one HA device entry."""
    await setup_integration_with_node_fixture(
        hass,
        "air-purifier",
        matter_client,
    )
    dev_reg = dr.async_get(hass)
    assert len(dev_reg.devices) == 1


async def test_get_clean_name_() -> None:
    """Test get_clean_name helper.

    Test device names that are assigned to `null`
    or have a trailing null char with spaces.
    """
    assert get_clean_name(None) is None
    assert get_clean_name("\x00") is None
    assert get_clean_name("   \x00") is None
    assert get_clean_name("") is None
    assert get_clean_name("Mock device") == "Mock device"
    assert get_clean_name("Mock device                    \x00") == "Mock device"
