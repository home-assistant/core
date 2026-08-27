"""Test the adapter."""

from unittest.mock import MagicMock

from matter_server.client.models.node import MatterNode
from matter_server.common.models import EventType
import pytest

from homeassistant.components.matter.adapter import get_clean_name
from homeassistant.components.matter.const import DOMAIN, ID_TYPE_DEVICE_ID
from homeassistant.components.matter.helpers import get_device_id
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import create_node_from_fixture

from tests.common import MockConfigEntry


def identifier_for(
    matter_client: MagicMock, node: MatterNode, endpoint_id: int
) -> tuple[str, str]:
    """Return the device registry identifier for a node endpoint."""
    device_id = get_device_id(matter_client.server_info, node.endpoints[endpoint_id])
    return (DOMAIN, f"{ID_TYPE_DEVICE_ID}_{device_id}")


def fire_endpoint_event(
    matter_client: MagicMock, event: EventType, node: MatterNode, endpoint_id: int
) -> None:
    """Fire an endpoint added/removed event for a node endpoint."""
    callback = next(
        call.kwargs["callback"]
        for call in matter_client.subscribe_events.call_args_list
        if call.kwargs["event_filter"] == event
    )
    callback(event, {"node_id": node.node_id, "endpoint_id": endpoint_id})


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize(
    ("node_fixture", "unique_id", "name"),
    [
        ("mock_onoff_light", "000000000000001E", "Mock OnOff Light"),
        ("mock_onoff_light_alt_name", "000000000000001B", "Mock OnOff Light"),
        ("mock_onoff_light_no_name", "000000000000001C", "Mock Light"),
    ],
)
async def test_device_registry_single_node_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    unique_id: str,
    name: str,
) -> None:
    """Test bridge devices are set up correctly with via_device."""
    entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"deviceid_00000000000004D2-{unique_id}-MatterNodeDevice"),
        hass.config_entries.async_entries(DOMAIN)[0].entry_id,
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
@pytest.mark.parametrize("node_fixture", ["mock_on_off_plugin_unit"])
async def test_device_registry_single_node_device_alt(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test additional device with different attribute values."""
    entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "deviceid_00000000000004D2-000000000000001A-MatterNodeDevice"),
        hass.config_entries.async_entries(DOMAIN)[0].entry_id,
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
    bridge_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "mock-hub-id"), hass.config_entries.async_entries(DOMAIN)[0].entry_id
    )
    assert bridge_entry is not None

    assert bridge_entry.name == "My Mock Bridge"
    assert bridge_entry.manufacturer == "Mock Vendor"
    assert bridge_entry.model == "Mock Bridge"
    assert bridge_entry.hw_version == "TEST_VERSION"
    assert bridge_entry.sw_version == "123.4.5"

    # Device 1
    device1_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "mock-id-kitchen-ceiling"),
        hass.config_entries.async_entries(DOMAIN)[0].entry_id,
    )
    assert device1_entry is not None

    assert device1_entry.via_device_id == bridge_entry.id
    assert device1_entry.name == "Kitchen Ceiling"
    assert device1_entry.manufacturer == "Mock Vendor"
    assert device1_entry.model == "Mock Light"
    assert device1_entry.hw_version is None
    assert device1_entry.sw_version == "67.8.9"

    # Device 2
    device2_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "mock-id-living-room-ceiling"),
        hass.config_entries.async_entries(DOMAIN)[0].entry_id,
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
    node = create_node_from_fixture("mock_onoff_light")

    entity_state = hass.states.get("light.mock_onoff_light")
    assert not entity_state

    node_added_callback(EventType.NODE_ADDED, node)
    await hass.async_block_till_done()

    entity_state = hass.states.get("light.mock_onoff_light")
    assert entity_state


async def test_endpoint_added_sets_up_bridge_before_child(
    hass: HomeAssistant,
    matter_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    integration: MockConfigEntry,
) -> None:
    """Test a bridged child endpoint resolves via_device_id set up out of order.

    The bridge device (endpoint 0) must be registered before a bridged child
    endpoint, even if the child's ENDPOINT_ADDED event is the only one that
    arrives (the bridge itself was never separately set up).
    """
    node = create_node_from_fixture("atios_knx_bridge")
    matter_client.get_node.return_value = node

    assert (
        device_registry.async_get_device_by_identifier(
            identifier_for(matter_client, node, 0), integration.entry_id
        )
        is None
    )

    fire_endpoint_event(matter_client, EventType.ENDPOINT_ADDED, node, 29)
    await hass.async_block_till_done()

    bridge_entry = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, node, 0), integration.entry_id
    )
    assert bridge_entry is not None

    child_entry = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, node, 29), integration.entry_id
    )
    assert child_entry is not None
    assert child_entry.via_device_id == bridge_entry.id


async def test_setup_node_sorts_bridge_before_child(
    hass: HomeAssistant,
    matter_client: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test initial node setup registers the bridge before a bridged child.

    Endpoints must be processed in endpoint-id order on the startup path
    (`_setup_node`), even when the bridged child endpoint precedes endpoint 0
    in the node's raw endpoint order, otherwise resolving the child's
    via_device_id would raise.
    """
    node = create_node_from_fixture("atios_knx_bridge")
    node.endpoints = {
        endpoint_id: node.endpoints[endpoint_id] for endpoint_id in (29, 1, 0)
    }

    matter_client.get_nodes.return_value = [node]
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={"url": "ws://localhost:5580/ws"}
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    bridge_entry = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, node, 0), config_entry.entry_id
    )
    assert bridge_entry is not None

    child_entry = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, node, 29), config_entry.entry_id
    )
    assert child_entry is not None
    assert child_entry.via_device_id == bridge_entry.id


@pytest.mark.parametrize("node_fixture", ["mock_composed_bridge"])
async def test_device_registry_composed_bridged_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test a composed device behind a bridge creates a single device entry.

    All endpoints of the composed device (the `BridgedNode` parent endpoint 2 and
    its part endpoints 3 and 4) must resolve to the same device entry, derived
    from the compose parent.
    """
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    bridge_entry = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, matter_node, 0), entry_id
    )
    assert bridge_entry is not None
    assert bridge_entry.name == "Mock Bridge"

    # the part endpoints 3 and 4 are represented by the device of their compose parent
    identifier = identifier_for(matter_client, matter_node, 2)
    assert identifier_for(matter_client, matter_node, 3) == identifier
    assert identifier_for(matter_client, matter_node, 4) == identifier

    device_entry = device_registry.async_get_device_by_identifier(identifier, entry_id)
    assert device_entry is not None
    assert device_entry.id != bridge_entry.id
    assert device_entry.via_device_id == bridge_entry.id
    assert device_entry.name == "Kitchen Plug"
    assert device_entry.model == "Mock Bridged Plug"
    assert device_entry.serial_number == "MBP-5678"

    assert len(device_registry.devices) == 2
    assert hass.states.get("switch.kitchen_plug")
    assert hass.states.get("sensor.kitchen_plug_temperature")


@pytest.mark.parametrize("node_fixture", ["mock_composed_bridge"])
async def test_composed_bridged_device_child_endpoint_added(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test a part endpoint of a composed bridged device keeps the via_device."""
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    bridge_entry = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, matter_node, 0), entry_id
    )
    assert bridge_entry is not None

    fire_endpoint_event(matter_client, EventType.ENDPOINT_ADDED, matter_node, 3)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, matter_node, 3), entry_id
    )
    assert device_entry is not None
    assert device_entry.via_device_id == bridge_entry.id


@pytest.mark.parametrize("node_fixture", ["mock_composed_bridge"])
async def test_composed_bridged_device_endpoint_removed(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test the device of a composed bridged device is removed with its parent.

    Removing a single part endpoint must not remove the device entry that the
    other endpoints of the composed device are still represented by.
    """
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    identifier = identifier_for(matter_client, matter_node, 2)

    fire_endpoint_event(matter_client, EventType.ENDPOINT_REMOVED, matter_node, 3)
    await hass.async_block_till_done()
    assert (
        device_registry.async_get_device_by_identifier(identifier, entry_id) is not None
    )

    fire_endpoint_event(matter_client, EventType.ENDPOINT_REMOVED, matter_node, 2)
    await hass.async_block_till_done()
    assert device_registry.async_get_device_by_identifier(identifier, entry_id) is None


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["atios_knx_bridge"])
@pytest.mark.parametrize(
    "attributes", [{"29/57/15": "glg5mxh"}], ids=["bridge_serial_number"]
)
async def test_device_registry_bridged_device_with_bridge_serial_number(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a bridged device reporting the serial number of the bridge itself.

    The serial number identifier must be skipped, as it would otherwise resolve
    to the bridge's own device entry.
    """
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    bridge_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "deviceid_00000000000004D2-000000000000003E-MatterNodeDevice"),
        entry_id,
    )
    assert bridge_entry is not None
    assert (DOMAIN, "serial_glg5mxh") in bridge_entry.identifiers

    bridged_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "deviceid_00000000000004D2-000000000000003E-29"), entry_id
    )
    assert bridged_entry is not None
    assert bridged_entry.id != bridge_entry.id
    assert bridged_entry.via_device_id == bridge_entry.id
    assert (DOMAIN, "serial_glg5mxh") not in bridged_entry.identifiers
    assert bridged_entry.serial_number is None


async def test_device_registry_bridged_device_merged_into_bridge(
    hass: HomeAssistant,
    matter_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a bridged device that was merged into the bridge's device is split off.

    A bridged device reporting the serial number of the bridge used to be merged
    into the bridge's device entry, which keeps resolving to it through the
    identifier that is left behind there.
    """
    node = create_node_from_fixture("atios_knx_bridge", {"29/57/15": "glg5mxh"})
    matter_client.get_nodes.return_value = [node]
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={"url": "ws://localhost:5580/ws"}
    )
    config_entry.add_to_hass(hass)

    merged_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-000000000000003E-MatterNodeDevice"),
            (DOMAIN, "deviceid_00000000000004D2-000000000000003E-29"),
            (DOMAIN, "serial_glg5mxh"),
        },
    )
    entity_entry = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "00000000000004D2-000000000000003E-29-29-ElectricalPowerMeasurementWatt-144-8",
        config_entry=config_entry,
        device_id=merged_entry.id,
        suggested_object_id="electricity_monitor_ac_power",
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    bridge_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "deviceid_00000000000004D2-000000000000003E-MatterNodeDevice"),
        config_entry.entry_id,
    )
    assert bridge_entry is not None
    assert bridge_entry.id == merged_entry.id
    assert (DOMAIN, "serial_glg5mxh") in bridge_entry.identifiers

    bridged_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "deviceid_00000000000004D2-000000000000003E-29"), config_entry.entry_id
    )
    assert bridged_entry is not None
    assert bridged_entry.id != bridge_entry.id
    assert bridged_entry.via_device_id == bridge_entry.id
    assert hass.states.get("sensor.electricity_monitor_ac_power")

    # the entities of the bridged device move to the device it is split off into
    assert (
        entity_registry.async_get(entity_entry.entity_id).device_id == bridged_entry.id
    )


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["mock_air_purifier"])
async def test_device_registry_single_node_composed_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test composed device in standalone node creates one device entry."""
    assert len(device_registry.devices) == 1


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
    good_node = create_node_from_fixture("mock_onoff_light")
    bad_node = create_node_from_fixture("mock_onoff_light")
    del bad_node.endpoints[0].node
    matter_client.get_nodes.return_value = [good_node, bad_node]
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={"url": "http://mock-matter-server-url"}
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert matter_client.get_nodes.call_count == 1
    assert hass.states.get("light.mock_onoff_light") is not None
    assert len(hass.states.async_all("light")) == 1
    assert "Error setting up node" in caplog.text


@pytest.mark.parametrize("node_fixture", ["mock_composed_bridge"])
@pytest.mark.parametrize(
    "attributes", [{"2/57/15": "MB-1234"}], ids=["bridge_serial_number"]
)
async def test_composed_bridged_device_with_bridge_serial_number(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test a composed bridged device reporting the serial number of the bridge."""
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    bridge_entry = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, matter_node, 0), entry_id
    )
    assert bridge_entry is not None

    # the part endpoints 3 and 4 are represented by the device of their compose parent
    identifier = identifier_for(matter_client, matter_node, 2)
    assert identifier_for(matter_client, matter_node, 3) == identifier
    assert identifier_for(matter_client, matter_node, 4) == identifier

    device_entry = device_registry.async_get_device_by_identifier(identifier, entry_id)
    assert device_entry is not None
    assert device_entry.id != bridge_entry.id
    assert device_entry.via_device_id == bridge_entry.id
    assert (DOMAIN, "serial_MB-1234") not in device_entry.identifiers


async def test_device_registry_bridged_device_merged_with_changed_bridge_serial(
    hass: HomeAssistant,
    matter_client: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test splitting off a merged bridged device after the bridge's serial changed.

    The bridge's device entry keeps the shared serial number identifier, so the
    bridged device has to be split off from it by all of its identifiers, not just
    its device ID, or it resolves to the bridge again through that serial number.
    """
    node = create_node_from_fixture(
        "atios_knx_bridge", {"0/40/15": "b7hcpwo", "29/57/15": "glg5mxh"}
    )
    matter_client.get_nodes.return_value = [node]
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={"url": "ws://localhost:5580/ws"}
    )
    config_entry.add_to_hass(hass)

    merged_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-000000000000003E-MatterNodeDevice"),
            (DOMAIN, "deviceid_00000000000004D2-000000000000003E-29"),
            (DOMAIN, "serial_glg5mxh"),
        },
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    bridge_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "deviceid_00000000000004D2-000000000000003E-MatterNodeDevice"),
        config_entry.entry_id,
    )
    assert bridge_entry is not None
    assert bridge_entry.id == merged_entry.id
    # the bridge keeps its own serial number, the stale one goes to the bridged device
    assert (DOMAIN, "serial_b7hcpwo") in bridge_entry.identifiers
    assert (DOMAIN, "serial_glg5mxh") not in bridge_entry.identifiers

    bridged_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "deviceid_00000000000004D2-000000000000003E-29"), config_entry.entry_id
    )
    assert bridged_entry is not None
    assert bridged_entry.id != bridge_entry.id
    assert bridged_entry.via_device_id == bridge_entry.id
    assert (DOMAIN, "serial_glg5mxh") in bridged_entry.identifiers


async def test_device_registry_bridged_device_split_off_with_changed_bridge_serial(
    hass: HomeAssistant,
    matter_client: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a bridged device that already has its own entry when the serial changes.

    The bridge's device entry still holds the serial number it shared with the
    bridged device, so that identifier has to be taken from it once the bridged
    device reports it as its own again.
    """
    node = create_node_from_fixture(
        "atios_knx_bridge", {"0/40/15": "b7hcpwo", "29/57/15": "glg5mxh"}
    )
    matter_client.get_nodes.return_value = [node]
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={"url": "ws://localhost:5580/ws"}
    )
    config_entry.add_to_hass(hass)

    bridge = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={
            (DOMAIN, "deviceid_00000000000004D2-000000000000003E-MatterNodeDevice"),
            (DOMAIN, "serial_glg5mxh"),
        },
    )
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "deviceid_00000000000004D2-000000000000003E-29")},
        via_device_id=bridge.id,
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    bridge_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "deviceid_00000000000004D2-000000000000003E-MatterNodeDevice"),
        config_entry.entry_id,
    )
    assert bridge_entry is not None
    assert (DOMAIN, "serial_b7hcpwo") in bridge_entry.identifiers
    assert (DOMAIN, "serial_glg5mxh") not in bridge_entry.identifiers

    bridged_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "deviceid_00000000000004D2-000000000000003E-29"), config_entry.entry_id
    )
    assert bridged_entry is not None
    assert bridged_entry.id != bridge_entry.id
    assert bridged_entry.via_device_id == bridge_entry.id
    assert (DOMAIN, "serial_glg5mxh") in bridged_entry.identifiers
