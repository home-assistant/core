"""Test the adapter."""

from __future__ import annotations

from unittest.mock import MagicMock

from matter_server.common.models import EventType
import pytest

from homeassistant.components.matter.adapter import get_clean_name
from homeassistant.components.matter.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .common import create_node_from_fixture

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize(
    ("node_fixture", "name"),
    [
        ("onoff_light", "Mock OnOff Light"),
        ("onoff_light_alt_name", "Mock OnOff Light"),
        ("onoff_light_no_name", "Mock Light"),
    ],
)
async def test_device_registry_single_node_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    name: str,
) -> None:
    """Test bridge devices are set up correctly with via_device."""
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
    assert entry.model_id == "32768"
    assert entry.hw_version == "v1.0"
    assert entry.sw_version == "v1.0"
    assert entry.serial_number == "12345678"


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["on_off_plugin_unit"])
async def test_device_registry_single_node_device_alt(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test additional device with different attribute values."""
    entry = device_registry.async_get_device(
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-0000000000000001-MatterNodeDevice")
        }
    )
    assert entry is not None

    # test name is derived from productName (because nodeLabel is absent)
    assert entry.name == "Mock OnOffPluginUnit"

    # test serial id NOT present as additional identifier
    assert (DOMAIN, "serial_TEST_SN") not in entry.identifiers
    assert entry.serial_number is None


@pytest.mark.usefixtures("matter_node")
@pytest.mark.skip("Waiting for a new test fixture")
@pytest.mark.parametrize("node_fixture", ["fake_bridge_two_light"])
async def test_device_registry_bridge(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test bridge devices are set up correctly with via_device."""
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


@pytest.mark.usefixtures("integration")
async def test_node_added_subscription(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Test subscription to new devices work."""
    assert matter_client.subscribe_events.call_count == 5
    assert (
        matter_client.subscribe_events.call_args.kwargs["event_filter"]
        == EventType.NODE_UPDATED
    )

    node_added_callback = matter_client.subscribe_events.call_args.kwargs["callback"]
    node = create_node_from_fixture("onoff_light")

    entity_state = hass.states.get("light.mock_onoff_light_light")
    assert not entity_state

    node_added_callback(EventType.NODE_ADDED, node)
    await hass.async_block_till_done()

    entity_state = hass.states.get("light.mock_onoff_light_light")
    assert entity_state


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["air_purifier"])
async def test_device_registry_single_node_composed_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that a composed device within a standalone node only creates one HA device entry."""
    assert len(device_registry.devices) == 1


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["multi_endpoint_light"])
async def test_multi_endpoint_name(hass: HomeAssistant) -> None:
    """Test that the entity name gets postfixed if the device has multiple primary endpoints."""
    entity_state = hass.states.get("light.inovelli_light_1")
    assert entity_state
    assert entity_state.name == "Inovelli Light (1)"
    entity_state = hass.states.get("light.inovelli_light_6")
    assert entity_state
    assert entity_state.name == "Inovelli Light (6)"


async def test_get_clean_name() -> None:
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


async def test_bad_node_not_crash_integration(
    hass: HomeAssistant,
    matter_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a bad node does not crash the integration."""
    good_node = create_node_from_fixture("onoff_light")
    bad_node = create_node_from_fixture("onoff_light")
    del bad_node.endpoints[0].node
    matter_client.get_nodes.return_value = [good_node, bad_node]
    config_entry = MockConfigEntry(
        domain="matter", data={"url": "http://mock-matter-server-url"}
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert matter_client.get_nodes.call_count == 1
    assert hass.states.get("light.mock_onoff_light_light") is not None
    assert len(hass.states.async_all("light")) == 1
    assert "Error setting up node" in caplog.text
