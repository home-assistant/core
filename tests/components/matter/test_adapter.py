"""Test the adapter."""

from unittest.mock import MagicMock, patch

from matter_server.client.models.node import MatterNode
from matter_server.common.models import EventType
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.matter.const import DOMAIN, ID_TYPE_DEVICE_ID
from homeassistant.components.matter.helpers import get_child_device_id, get_device_id
from homeassistant.components.matter.semantic_tags import (
    POSITION_BOTTOM,
    POSITION_LEFT,
    POSITION_RIGHT,
    POSITION_TOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import (
    EVE_ENERGY_LIGHT_PART_ATTRIBUTES,
    TAPO_STRIP_NUMBER_TAG_ATTRIBUTES,
    create_node_from_fixture,
    load_and_parse_node_fixture,
    set_node_attribute,
)


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
        for call in reversed(matter_client.subscribe_events.call_args_list)
        if call.kwargs["event_filter"] == event
    )
    callback(event, {"node_id": node.node_id, "endpoint_id": endpoint_id})


def remove_endpoint(
    matter_client: MagicMock, node: MatterNode, endpoint_id: int
) -> None:
    """Remove an endpoint the way the client does.

    The client calls the ENDPOINT_REMOVED subscribers first and then drops the
    endpoint together with its composed parts and their compose relations.
    """
    fire_endpoint_event(matter_client, EventType.ENDPOINT_REMOVED, node, endpoint_id)
    node._remove_endpoint(endpoint_id)


def fire_node_removed_event(matter_client: MagicMock, node: MatterNode) -> None:
    """Fire a node removed event for a node."""
    callback = next(
        call.kwargs["callback"]
        for call in reversed(matter_client.subscribe_events.call_args_list)
        if call.kwargs["event_filter"] == EventType.NODE_REMOVED
    )
    callback(EventType.NODE_REMOVED, node.node_id)


def fire_node_updated_event(matter_client: MagicMock, node: MatterNode) -> None:
    """Fire a node updated event for a node."""
    # The adapter's node-updated handler subscribes without a node_filter, unlike
    # the per-entity subscriptions that also listen for NODE_UPDATED.
    callback = next(
        call.kwargs["callback"]
        for call in reversed(matter_client.subscribe_events.call_args_list)
        if call.kwargs["event_filter"] == EventType.NODE_UPDATED
        and call.kwargs.get("node_filter") is None
    )
    callback(EventType.NODE_UPDATED, node)


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


@pytest.mark.parametrize("node_fixture", ["eve_energy_20ecn4101"])
async def test_endpoint_child_devices(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a multi-socket plug splits into a parent and per-socket child devices.

    The Eve Energy dual outlet exposes two On/Off Plug-in Unit endpoints (labeled
    ``top`` and ``bottom``). Each becomes its own child device of the node device,
    and its socket switch entity is placed on the child, not on the parent.
    """
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    parent = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, matter_node, 0), entry_id
    )
    assert parent is not None

    children = dr.async_entries_for_parent_device(device_registry, parent.id)
    assert {child.name for child in children} == {"Top", "Bottom"}
    children_by_name = {child.name: child for child in children}

    for name, endpoint_id, switch_entity_id in (
        ("Top", 1, "switch.eve_energy_20ecn4101_top"),
        ("Bottom", 2, "switch.eve_energy_20ecn4101_bottom"),
    ):
        child = children_by_name[name]
        assert child.parent_device_id == parent.id
        child_device_id = get_child_device_id(
            matter_client.server_info, matter_node.endpoints[endpoint_id]
        )
        assert (DOMAIN, f"{ID_TYPE_DEVICE_ID}_{child_device_id}") in child.identifiers
        # The socket switch entity lives on the child device, not the parent.
        switch_entry = entity_registry.async_get(switch_entity_id)
        assert switch_entry is not None
        assert switch_entry.device_id == child.id


@pytest.mark.parametrize("node_fixture", ["tp_link_smart_outdoor_plug"])
@pytest.mark.parametrize(
    "attributes",
    [
        {
            "1/64/0": [{"0": "Position", "1": "Garden"}],
            "2/64/0": [{"0": "Position", "1": "Patio"}],
        }
    ],
)
async def test_endpoint_child_devices_literal_names(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test vendor labels that aren't numbers or positions name child devices as is."""
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    parent = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, matter_node, 0), entry_id
    )
    assert parent is not None

    children = dr.async_entries_for_parent_device(device_registry, parent.id)
    assert {child.name for child in children} == {"Garden", "Patio"}
    switch_entry = entity_registry.async_get("switch.smart_outdoor_plug_garden")
    assert switch_entry is not None
    assert switch_entry.device_id == next(
        child.id for child in children if child.name == "Garden"
    )


@pytest.mark.parametrize("node_fixture", ["eve_energy_20ecn4101"])
async def test_endpoint_child_device_removed(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test removing a split endpoint removes only its child device."""
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    parent = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, matter_node, 0), entry_id
    )
    assert parent is not None
    assert len(dr.async_entries_for_parent_device(device_registry, parent.id)) == 2

    fire_endpoint_event(matter_client, EventType.ENDPOINT_REMOVED, matter_node, 1)

    children = dr.async_entries_for_parent_device(device_registry, parent.id)
    assert {child.name for child in children} == {"Bottom"}
    # The parent node device is untouched.
    assert (
        device_registry.async_get_device_by_identifier(
            identifier_for(matter_client, matter_node, 0), entry_id
        )
        is not None
    )


@pytest.mark.parametrize("node_fixture", ["eve_energy_20ecn4101"])
async def test_node_removed_removes_child_devices(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test removing the node removes the node device and all its child devices."""
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    parent = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, matter_node, 0), entry_id
    )
    assert parent is not None
    assert len(dr.async_entries_for_parent_device(device_registry, parent.id)) == 2

    fire_node_removed_event(matter_client, matter_node)

    # The node device and both of its child devices are gone.
    assert (
        device_registry.async_get_device_by_identifier(
            identifier_for(matter_client, matter_node, 0), entry_id
        )
        is None
    )
    for endpoint_id in (1, 2):
        child_device_id = get_child_device_id(
            matter_client.server_info, matter_node.endpoints[endpoint_id]
        )
        assert (
            device_registry.async_get_child_device_by_identifier(
                (DOMAIN, f"{ID_TYPE_DEVICE_ID}_{child_device_id}"), entry_id
            )
            is None
        )


@pytest.mark.parametrize("node_fixture", ["eve_energy_20ecn4101"])
async def test_endpoint_child_devices_pruned_on_setup(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test stale child devices are pruned when an endpoint no longer needs one."""
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    parent = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, matter_node, 0), entry_id
    )
    assert parent is not None
    assert len(dr.async_entries_for_parent_device(device_registry, parent.id)) == 2

    # Drop one socket so the remaining socket no longer has a same-type sibling
    # and stops needing its own child device, then re-run node setup.
    matter_node.endpoints.pop(2)
    fire_node_updated_event(matter_client, matter_node)
    await hass.async_block_till_done()

    # Both child devices are pruned. The surviving socket's switch moves back to
    # the node device, while the removed socket's switch is deleted.
    assert not dr.async_entries_for_parent_device(device_registry, parent.id)
    surviving_switch = entity_registry.async_get("switch.eve_energy_20ecn4101_top")
    assert surviving_switch is not None
    assert surviving_switch.device_id == parent.id
    assert entity_registry.async_get("switch.eve_energy_20ecn4101_bottom") is None


@pytest.mark.parametrize("node_fixture", ["eve_energy_20ecn4101"])
async def test_endpoint_child_devices_pruned_when_unnamed(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a group that can no longer be named stops splitting on node update.

    The config entry is reloaded, so the moved entities get the suffixed names
    of endpoints that don't split.
    """
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    parent = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, matter_node, 0), entry_id
    )
    assert parent is not None
    assert len(dr.async_entries_for_parent_device(device_registry, parent.id)) == 2

    # Drop the orientation label of the bottom socket, so it can't be named.
    set_node_attribute(matter_node, 2, 64, 0, [{"0": "id", "1": "2"}])
    fire_node_updated_event(matter_client, matter_node)
    await hass.async_block_till_done()

    # Both child devices are pruned and both switches move to the node device.
    assert not dr.async_entries_for_parent_device(device_registry, parent.id)
    for entity_id, name in (
        ("switch.eve_energy_20ecn4101_top", "Eve Energy 20ECN4101 Switch (top)"),
        ("switch.eve_energy_20ecn4101_bottom", "Eve Energy 20ECN4101 Switch (2)"),
    ):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.device_id == parent.id
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.name == name


@pytest.mark.parametrize("node_fixture", ["eve_energy_20ecn4101"])
@pytest.mark.parametrize("attributes", [{"1/319486977/319422472": None}])
async def test_endpoint_child_devices_pruned_with_new_entity(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a node update that stops a split and adds an entity reloads cleanly.

    The new entity is only created by the reload, not also by the node setup
    that schedules it, so its unique ID isn't added twice.
    """
    assert entity_registry.async_get("sensor.eve_energy_20ecn4101_voltage_top") is None

    # Drop the orientation label of the bottom socket, so it can't be named, and
    # report the voltage, which adds an entity.
    set_node_attribute(matter_node, 2, 64, 0, [{"0": "id", "1": "2"}])
    set_node_attribute(matter_node, 1, 319486977, 319422472, 123.0)
    fire_node_updated_event(matter_client, matter_node)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.eve_energy_20ecn4101_voltage_top")
    assert state is not None
    assert state.state == "123.0"
    assert "does not generate unique IDs" not in caplog.text


@pytest.mark.parametrize("node_fixture", ["eve_energy_20ecn4101"])
async def test_endpoint_child_devices_pruned_on_reload(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test stale child devices are pruned on setup without another reload."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    entry_id = entry.entry_id
    parent = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, matter_node, 0), entry_id
    )
    assert parent is not None
    children = dr.async_entries_for_parent_device(device_registry, parent.id)
    assert len(children) == 2
    # An entity that setup doesn't add again stays on the child device until the
    # child is pruned.
    orphan = entity_registry.async_get_or_create(
        "switch",
        DOMAIN,
        "orphan",
        config_entry=entry,
        device_id=next(child.id for child in children if child.name == "Bottom"),
    )

    # Drop the orientation label of the bottom socket, so it can't be named.
    set_node_attribute(matter_node, 2, 64, 0, [{"0": "id", "1": "2"}])
    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        assert await hass.config_entries.async_reload(entry_id)
        await hass.async_block_till_done()

    mock_reload.assert_not_called()
    assert not dr.async_entries_for_parent_device(device_registry, parent.id)
    orphan_entry = entity_registry.async_get(orphan.entity_id)
    assert orphan_entry is not None
    assert orphan_entry.device_id == parent.id


@pytest.mark.parametrize("node_fixture", ["lifx_switch_115"])
async def test_endpoint_child_devices_renamed_on_node_update(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test child devices are renamed when the names of a split group change.

    A child device is otherwise only renamed when one of its entities is added,
    which could leave siblings with names from different sources.
    """
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    parent = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, matter_node, 0), entry_id
    )
    assert parent is not None
    children = dr.async_entries_for_parent_device(device_registry, parent.id)
    assert {child.name for child in children} == {
        "Channel 1",
        "Channel 2",
        "Channel 3",
        "Channel 4",
    }

    # E.g. a firmware update replaces the Common Number tags by positions.
    for endpoint_id, tags in (
        (41, (POSITION_TOP, POSITION_LEFT)),
        (42, (POSITION_TOP, POSITION_RIGHT)),
        (43, (POSITION_BOTTOM, POSITION_LEFT)),
        (44, (POSITION_BOTTOM, POSITION_RIGHT)),
    ):
        set_node_attribute(
            matter_node,
            endpoint_id,
            29,
            4,
            [{"0": None, "1": 8, "2": tag} for tag in tags],
        )
    fire_node_updated_event(matter_client, matter_node)
    await hass.async_block_till_done()

    children = dr.async_entries_for_parent_device(device_registry, parent.id)
    assert {child.name for child in children} == {
        "Top left",
        "Top right",
        "Bottom left",
        "Bottom right",
    }


@pytest.mark.parametrize("node_fixture", ["eve_energy_20ecn4101"])
async def test_endpoint_child_devices_collapsed_on_reload(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a child device that collapsed while unloaded is pruned without a reload.

    The entities are created after the prune, so they already get the names of
    the node device.
    """
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    parent = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, matter_node, 0), entry_id
    )
    assert parent is not None
    assert await hass.config_entries.async_unload(entry_id)
    matter_node.endpoints.pop(2)

    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        assert await hass.config_entries.async_setup(entry_id)
        await hass.async_block_till_done()

    mock_reload.assert_not_called()
    assert not dr.async_entries_for_parent_device(device_registry, parent.id)
    state = hass.states.get("select.eve_energy_20ecn4101_top_power_on_behavior")
    assert state is not None
    assert state.name == "Eve Energy 20ECN4101 Power-on behavior (top)"


@pytest.mark.parametrize("node_fixture", ["eve_energy_20ecn4101"])
@pytest.mark.parametrize("attributes", [{"1/319486977/319422472": None}])
async def test_collapsed_with_new_entity_reloads_cleanly(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a node update that collapses a child and adds an entity reloads cleanly.

    The new entity is only created by the reload, not also by the node setup
    that schedules it, so its unique ID isn't added twice.
    """
    remove_endpoint(matter_client, matter_node, 2)
    set_node_attribute(matter_node, 1, 319486977, 319422472, 123.0)
    fire_node_updated_event(matter_client, matter_node)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.eve_energy_20ecn4101_voltage_top")
    assert state is not None
    assert state.state == "123.0"
    assert "does not generate unique IDs" not in caplog.text


@pytest.mark.parametrize("node_fixture", ["eve_energy_20ecn4101"])
async def test_collapsed_disabled_entities_dont_reload(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test moving only disabled entities to the node device doesn't reload."""
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    parent = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, matter_node, 0), entry_id
    )
    assert parent is not None
    for child in dr.async_entries_for_parent_device(device_registry, parent.id):
        for entity_entry in er.async_entries_for_device(entity_registry, child.id):
            entity_registry.async_update_entity(
                entity_entry.entity_id, disabled_by=er.RegistryEntryDisabler.USER
            )

    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        matter_node.endpoints.pop(2)
        fire_node_updated_event(matter_client, matter_node)
        await hass.async_block_till_done()

    mock_reload.assert_not_called()
    assert not dr.async_entries_for_parent_device(device_registry, parent.id)


@pytest.mark.parametrize("node_fixture", ["eve_energy_20ecn4101"])
async def test_pruned_collapsed_child_preserves_disabled_entities(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a disabled entity is migrated, not deleted, when its child collapses."""
    entity_registry.async_update_entity(
        "select.eve_energy_20ecn4101_top_power_on_behavior",
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    parent = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, matter_node, 0), entry_id
    )
    assert parent is not None

    # Collapse the top socket by removing its sibling, then re-run node setup.
    matter_node.endpoints.pop(2)
    fire_node_updated_event(matter_client, matter_node)
    await hass.async_block_till_done()

    migrated = entity_registry.async_get(
        "select.eve_energy_20ecn4101_top_power_on_behavior"
    )
    assert migrated is not None
    assert migrated.device_id == parent.id
    assert migrated.disabled_by is er.RegistryEntryDisabler.USER


@pytest.mark.parametrize("node_fixture", ["eve_energy_20ecn4101"])
async def test_pruned_disabled_entities_dont_reload(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test moving only disabled entities to the node device doesn't reload."""
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    parent = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, matter_node, 0), entry_id
    )
    assert parent is not None
    for child in dr.async_entries_for_parent_device(device_registry, parent.id):
        for entity_entry in er.async_entries_for_device(entity_registry, child.id):
            entity_registry.async_update_entity(
                entity_entry.entity_id, disabled_by=er.RegistryEntryDisabler.USER
            )

    # Drop the orientation label of the bottom socket, so it can't be named.
    set_node_attribute(matter_node, 2, 64, 0, [{"0": "id", "1": "2"}])
    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        fire_node_updated_event(matter_client, matter_node)
        await hass.async_block_till_done()

    mock_reload.assert_not_called()
    assert not dr.async_entries_for_parent_device(device_registry, parent.id)


@pytest.mark.parametrize("node_fixture", ["eve_energy_20ecn4101"])
async def test_endpoint_child_device_readded_after_removal(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a split endpoint's entities are rediscovered after remove and re-add."""
    assert entity_registry.async_get("switch.eve_energy_20ecn4101_top") is not None

    # Removing the endpoint deletes its child device and entities.
    fire_endpoint_event(matter_client, EventType.ENDPOINT_REMOVED, matter_node, 1)
    assert entity_registry.async_get("switch.eve_energy_20ecn4101_top") is None

    # Re-adding the endpoint rediscovers its entities instead of skipping them
    # until a reload.
    fire_endpoint_event(matter_client, EventType.ENDPOINT_ADDED, matter_node, 1)
    await hass.async_block_till_done()

    assert entity_registry.async_get("switch.eve_energy_20ecn4101_top") is not None


@pytest.mark.parametrize("node_fixture", ["eve_energy_20ecn4101"])
@pytest.mark.parametrize("attributes", [EVE_ENERGY_LIGHT_PART_ATTRIBUTES])
async def test_endpoint_child_device_with_part_removed_and_readded(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a split endpoint's parts are removed and re-added with it."""
    light_entity_id = "light.eve_energy_20ecn4101_top_light_3"
    assert entity_registry.async_get(light_entity_id) is not None

    remove_endpoint(matter_client, matter_node, 1)
    assert entity_registry.async_get(light_entity_id) is None

    fire_node_updated_event(matter_client, matter_node)
    await hass.async_block_till_done()
    matter_node.update(matter_node.node_data)
    fire_node_updated_event(matter_client, matter_node)
    fire_endpoint_event(matter_client, EventType.ENDPOINT_ADDED, matter_node, 1)
    await hass.async_block_till_done()

    switch_entry = entity_registry.async_get("switch.eve_energy_20ecn4101_top")
    assert switch_entry is not None
    light_entry = entity_registry.async_get(light_entity_id)
    assert light_entry is not None
    assert light_entry.device_id == switch_entry.device_id


@pytest.mark.parametrize("node_fixture", ["eve_energy_20ecn4101"])
@pytest.mark.parametrize("attributes", [EVE_ENERGY_LIGHT_PART_ATTRIBUTES])
async def test_endpoint_child_device_part_removed_first(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a split endpoint's part announced as removed first is removed."""
    light_entity_id = "light.eve_energy_20ecn4101_top_light_3"
    assert entity_registry.async_get(light_entity_id) is not None

    for endpoint_id in (3, 1):
        remove_endpoint(matter_client, matter_node, endpoint_id)
    assert entity_registry.async_get(light_entity_id) is None
    assert entity_registry.async_get("switch.eve_energy_20ecn4101_top") is None


@pytest.mark.parametrize("node_fixture", ["eve_energy_20ecn4101"])
async def test_node_device_cluster_entities_removed_with_endpoint(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test Eve cluster entities stay on the node device and go with the endpoint."""
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    parent = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, matter_node, 0), entry_id
    )
    assert parent is not None
    power_entity_id = "sensor.eve_energy_20ecn4101_power_top"
    power_entry = entity_registry.async_get(power_entity_id)
    assert power_entry is not None
    assert power_entry.device_id == parent.id

    remove_endpoint(matter_client, matter_node, 1)
    assert entity_registry.async_get(power_entity_id) is None
    fire_node_updated_event(matter_client, matter_node)
    await hass.async_block_till_done()

    matter_node.update(matter_node.node_data)
    fire_node_updated_event(matter_client, matter_node)
    fire_endpoint_event(matter_client, EventType.ENDPOINT_ADDED, matter_node, 1)
    await hass.async_block_till_done()

    power_entry = entity_registry.async_get(power_entity_id)
    assert power_entry is not None
    assert power_entry.device_id == parent.id
    assert "does not generate unique IDs" not in caplog.text


@pytest.mark.parametrize("node_fixture", ["eve_energy_20ecn4101"])
async def test_node_device_cluster_entities_pruned_with_endpoint(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Eve cluster entities go with an endpoint that vanished while unloaded."""
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    assert entity_registry.async_get("sensor.eve_energy_20ecn4101_power_top")
    assert await hass.config_entries.async_unload(entry_id)
    matter_node.endpoints.pop(1)

    assert await hass.config_entries.async_setup(entry_id)
    await hass.async_block_till_done()

    for entity_id in (
        "sensor.eve_energy_20ecn4101_power_top",
        "switch.eve_energy_20ecn4101_child_lock_top",
        "switch.eve_energy_20ecn4101_top",
    ):
        assert entity_registry.async_get(entity_id) is None


@pytest.mark.parametrize("node_fixture", ["eve_energy_20ecn4101"])
@pytest.mark.parametrize(
    "attributes",
    [
        {
            **{
                f"2/319486977/{attribute_id}": value
                for path, value in load_and_parse_node_fixture("eve_energy_20ecn4101")[
                    "attributes"
                ].items()
                if path.startswith("1/319486977/")
                and (attribute_id := path.rsplit("/", 1)[1])
            },
            "2/29/1": [3, 4, 6, 29, 64, 319486977],
            "1/64/0": [{"0": "id", "1": "1"}],
            "2/64/0": [{"0": "id", "1": "2"}],
            # Name the outlets, so they split.
            "1/29/65532": 1,
            "2/29/65532": 1,
            "1/29/4": [{"0": None, "1": 7, "2": 1}],
            "2/29/4": [{"0": None, "1": 7, "2": 2}],
        }
    ],
)
async def test_node_device_cluster_entities_on_several_endpoints(
    hass: HomeAssistant,
    matter_node: MatterNode,
) -> None:
    """Test Eve cluster entities of several split endpoints keep endpoint suffixes."""
    names = {
        state.name
        for state in hass.states.async_all("sensor")
        if state.name.startswith("Eve Energy 20ECN4101 Power")
    }
    assert names == {
        "Eve Energy 20ECN4101 Power (1)",
        "Eve Energy 20ECN4101 Power (2)",
    }


@pytest.mark.parametrize("node_fixture", ["eve_energy_20ecn4101"])
async def test_endpoint_child_device_readded_after_node_update(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test both sockets split again after one is removed and re-added.

    The client pops the endpoint after the ENDPOINT_REMOVED callbacks, and the
    server sends NODE_UPDATED after the removal and before ENDPOINT_ADDED.
    """
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    parent = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, matter_node, 0), entry_id
    )
    assert parent is not None

    fire_endpoint_event(matter_client, EventType.ENDPOINT_REMOVED, matter_node, 1)
    endpoint = matter_node.endpoints.pop(1)
    fire_node_updated_event(matter_client, matter_node)
    await hass.async_block_till_done()

    # The bottom socket no longer has a sibling, so it collapses onto the parent.
    bottom = entity_registry.async_get("switch.eve_energy_20ecn4101_bottom")
    assert bottom is not None
    assert bottom.device_id == parent.id

    matter_node.endpoints[1] = endpoint
    fire_node_updated_event(matter_client, matter_node)
    fire_endpoint_event(matter_client, EventType.ENDPOINT_ADDED, matter_node, 1)
    await hass.async_block_till_done()

    children = dr.async_entries_for_parent_device(device_registry, parent.id)
    assert {child.name for child in children} == {"Top", "Bottom"}
    for entity_id in (
        "switch.eve_energy_20ecn4101_top",
        "switch.eve_energy_20ecn4101_bottom",
    ):
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry is not None
        assert entity_entry.device_id in {child.id for child in children}


@pytest.mark.parametrize(
    ("node_fixture", "attributes", "endpoint_id"),
    [
        pytest.param("eve_energy_20ecn4101", {}, 1, id="split_endpoint"),
        pytest.param(
            "tapo_smart_wi_fi_power_strip",
            TAPO_STRIP_NUMBER_TAG_ATTRIBUTES,
            7,
            id="power_topology",
        ),
    ],
)
async def test_endpoint_added_without_placement_change_does_not_reload(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    endpoint_id: int,
) -> None:
    """Test adding an endpoint doesn't reload when all entities are in place."""
    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        fire_endpoint_event(
            matter_client, EventType.ENDPOINT_ADDED, matter_node, endpoint_id
        )
        await hass.async_block_till_done()

    mock_reload.assert_not_called()


@pytest.mark.parametrize("node_fixture", ["eve_energy_20ecn4101"])
async def test_endpoint_added_with_placement_change_reloads_once(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test re-adding a socket after its sibling collapsed reloads the entry once."""
    fire_endpoint_event(matter_client, EventType.ENDPOINT_REMOVED, matter_node, 1)
    endpoint = matter_node.endpoints.pop(1)
    fire_node_updated_event(matter_client, matter_node)
    await hass.async_block_till_done()
    matter_node.endpoints[1] = endpoint

    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        fire_node_updated_event(matter_client, matter_node)
        fire_endpoint_event(matter_client, EventType.ENDPOINT_ADDED, matter_node, 1)
        await hass.async_block_till_done()

    mock_reload.assert_called_once()


@pytest.mark.parametrize("node_fixture", ["eve_energy_20ecn4101"])
async def test_endpoint_child_devices_readded_after_consecutive_removal(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test both sockets are rediscovered after being removed one after the other.

    When the second socket is removed, it has no sibling left and no longer
    splits, but its entities are still removed with its child device.
    """
    endpoints = {}
    for endpoint_id in (1, 2):
        fire_endpoint_event(
            matter_client, EventType.ENDPOINT_REMOVED, matter_node, endpoint_id
        )
        endpoints[endpoint_id] = matter_node.endpoints.pop(endpoint_id)
    assert entity_registry.async_get("switch.eve_energy_20ecn4101_top") is None
    assert entity_registry.async_get("switch.eve_energy_20ecn4101_bottom") is None

    matter_node.endpoints.update(endpoints)
    for endpoint_id in (1, 2):
        fire_endpoint_event(
            matter_client, EventType.ENDPOINT_ADDED, matter_node, endpoint_id
        )
    await hass.async_block_till_done()

    assert entity_registry.async_get("switch.eve_energy_20ecn4101_top") is not None
    assert entity_registry.async_get("switch.eve_energy_20ecn4101_bottom") is not None


@pytest.mark.parametrize("node_fixture", ["eve_energy_20ecn4101"])
async def test_collapsed_endpoint_removed_keeps_node_device(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test removing an endpoint on the node device removes only its entities."""
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    parent = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, matter_node, 0), entry_id
    )
    assert parent is not None

    for endpoint_id in (1, 2):
        fire_endpoint_event(
            matter_client, EventType.ENDPOINT_REMOVED, matter_node, endpoint_id
        )
        matter_node.endpoints.pop(endpoint_id)
        fire_node_updated_event(matter_client, matter_node)
        await hass.async_block_till_done()

    assert entity_registry.async_get("switch.eve_energy_20ecn4101_bottom") is None
    assert device_registry.async_get(parent.id) is not None
    reboot_count = entity_registry.async_get("sensor.eve_energy_20ecn4101_reboot_count")
    assert reboot_count is not None
    assert reboot_count.device_id == parent.id


async def test_existing_endpoint_entities_move_to_child_devices(
    hass: HomeAssistant,
    matter_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entities registered on the node device move to their child device.

    Their entity IDs and customizations are kept, also for a disabled entity.
    """
    node = create_node_from_fixture("eve_energy_20ecn4101")
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={"url": "http://mock-matter-server-url"}
    )
    config_entry.add_to_hass(hass)
    parent = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={identifier_for(matter_client, node, 0)},
    )
    switch_entry = entity_registry.async_get_or_create(
        "switch",
        DOMAIN,
        "00000000000004D2-00000000000000C7-MatterNodeDevice-1-MatterPlug-6-0",
        config_entry=config_entry,
        device_id=parent.id,
        suggested_object_id="eve_energy_20ecn4101_switch_1",
    )
    entity_registry.async_update_entity(switch_entry.entity_id, name="Kettle")
    power_entry = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "00000000000004D2-00000000000000C7-MatterNodeDevice-1-"
        "EveEnergySensorWatt-319486977-319422474",
        config_entry=config_entry,
        device_id=parent.id,
        suggested_object_id="eve_energy_20ecn4101_power_1",
    )
    child_lock_entry = entity_registry.async_get_or_create(
        "switch",
        DOMAIN,
        "00000000000004D2-00000000000000C7-MatterNodeDevice-1-"
        "EveChildLock-319486977-319422481",
        config_entry=config_entry,
        device_id=parent.id,
        suggested_object_id="eve_energy_20ecn4101_child_lock_1",
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    power_on_entry = entity_registry.async_get_or_create(
        "select",
        DOMAIN,
        "00000000000004D2-00000000000000C7-MatterNodeDevice-1-"
        "MatterStartUpOnOff-6-16387",
        config_entry=config_entry,
        device_id=parent.id,
        suggested_object_id="eve_energy_20ecn4101_power_on_behavior_1",
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    matter_client.get_nodes.return_value = [node]
    matter_client.get_node.return_value = node

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    top = device_registry.async_get_child_device_by_identifier(
        (
            DOMAIN,
            f"{ID_TYPE_DEVICE_ID}_"
            f"{get_child_device_id(matter_client.server_info, node.endpoints[1])}",
        ),
        config_entry.entry_id,
    )
    assert top is not None
    assert top.parent_device_id == parent.id
    switch_entry = entity_registry.async_get(switch_entry.entity_id)
    assert switch_entry is not None
    assert switch_entry.entity_id == "switch.eve_energy_20ecn4101_switch_1"
    assert switch_entry.name == "Kettle"
    assert switch_entry.device_id == top.id
    power_on_entry = entity_registry.async_get(power_on_entry.entity_id)
    assert power_on_entry is not None
    assert power_on_entry.disabled_by is er.RegistryEntryDisabler.USER
    assert power_on_entry.device_id == top.id
    # The Eve cluster's entities cover the whole device and stay on it.
    power_entry = entity_registry.async_get(power_entry.entity_id)
    assert power_entry is not None
    assert power_entry.entity_id == "sensor.eve_energy_20ecn4101_power_1"
    assert power_entry.device_id == parent.id
    child_lock_entry = entity_registry.async_get(child_lock_entry.entity_id)
    assert child_lock_entry is not None
    assert child_lock_entry.disabled_by is er.RegistryEntryDisabler.USER
    assert child_lock_entry.device_id == parent.id


TAPO_STRIP_SWITCH_1 = "switch.smart_wi_fi_power_strip_channel_1"
TAPO_STRIP_POWER_1 = "sensor.smart_wi_fi_power_strip_channel_1_power"


@pytest.mark.parametrize("node_fixture", ["tapo_smart_wi_fi_power_strip"])
@pytest.mark.parametrize("attributes", [TAPO_STRIP_NUMBER_TAG_ATTRIBUTES])
async def test_power_topology_entities_on_measured_child_device(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a measurement endpoint's entities join the child of the outlet it measures.

    Each outlet (endpoints 1 to 6) of the power strip has an Electrical Sensor
    endpoint (7 to 12) whose Power Topology lists only that outlet.
    """
    switch_entry = entity_registry.async_get(TAPO_STRIP_SWITCH_1)
    assert switch_entry is not None
    child = device_registry.async_get(switch_entry.device_id)
    assert isinstance(child, dr.ChildDeviceEntry)
    child_device_id = get_child_device_id(
        matter_client.server_info, matter_node.endpoints[1]
    )
    assert (DOMAIN, f"{ID_TYPE_DEVICE_ID}_{child_device_id}") in child.identifiers

    power_entry = entity_registry.async_get(TAPO_STRIP_POWER_1)
    assert power_entry is not None
    assert power_entry.device_id == child.id
    # The unique ID still refers to the measurement endpoint.
    assert power_entry.unique_id.startswith(
        f"{get_device_id(matter_client.server_info, matter_node.endpoints[7])}-7-"
    )
    # No endpoint suffix, as the child device names the outlet.
    assert power_entry.original_name == "Power"


@pytest.mark.parametrize("node_fixture", ["tapo_smart_wi_fi_power_strip"])
@pytest.mark.parametrize("attributes", [TAPO_STRIP_NUMBER_TAG_ATTRIBUTES])
async def test_power_topology_endpoint_removed_and_readded(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test removing a measurement endpoint removes only its own entities."""
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    parent = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, matter_node, 0), entry_id
    )
    assert parent is not None

    fire_endpoint_event(matter_client, EventType.ENDPOINT_REMOVED, matter_node, 7)
    endpoint = matter_node.endpoints.pop(7)
    fire_node_updated_event(matter_client, matter_node)
    await hass.async_block_till_done()

    assert entity_registry.async_get(TAPO_STRIP_POWER_1) is None
    # The outlet, its child device and the node device are untouched.
    switch_entry = entity_registry.async_get(TAPO_STRIP_SWITCH_1)
    assert switch_entry is not None
    assert device_registry.async_get(switch_entry.device_id) is not None
    assert device_registry.async_get(parent.id) is not None
    assert len(dr.async_entries_for_parent_device(device_registry, parent.id)) == 6

    matter_node.endpoints[7] = endpoint
    fire_node_updated_event(matter_client, matter_node)
    fire_endpoint_event(matter_client, EventType.ENDPOINT_ADDED, matter_node, 7)
    await hass.async_block_till_done()

    power_entry = entity_registry.async_get(TAPO_STRIP_POWER_1)
    assert power_entry is not None
    assert power_entry.device_id == switch_entry.device_id


@pytest.mark.parametrize("node_fixture", ["tapo_smart_wi_fi_power_strip"])
@pytest.mark.parametrize("attributes", [TAPO_STRIP_NUMBER_TAG_ATTRIBUTES])
async def test_power_topology_measured_endpoint_removed_and_readded(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the measurement entities follow their outlet when it returns."""
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    parent = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, matter_node, 0), entry_id
    )
    assert parent is not None

    # Removing the outlet removes its child device, but the measurement entities
    # stay and move to the node device, also without a later node update.
    fire_endpoint_event(matter_client, EventType.ENDPOINT_REMOVED, matter_node, 1)
    assert entity_registry.async_get(TAPO_STRIP_SWITCH_1) is None
    power_entry = entity_registry.async_get(TAPO_STRIP_POWER_1)
    assert power_entry is not None
    assert power_entry.device_id == parent.id

    endpoint = matter_node.endpoints.pop(1)
    fire_node_updated_event(matter_client, matter_node)
    await hass.async_block_till_done()

    power_entry = entity_registry.async_get(TAPO_STRIP_POWER_1)
    assert power_entry is not None
    assert power_entry.device_id == parent.id

    matter_node.endpoints[1] = endpoint
    fire_node_updated_event(matter_client, matter_node)
    fire_endpoint_event(matter_client, EventType.ENDPOINT_ADDED, matter_node, 1)
    await hass.async_block_till_done()

    switch_entry = entity_registry.async_get(TAPO_STRIP_SWITCH_1)
    assert switch_entry is not None
    power_entry = entity_registry.async_get(TAPO_STRIP_POWER_1)
    assert power_entry is not None
    assert power_entry.device_id == switch_entry.device_id


@pytest.mark.parametrize("node_fixture", ["tapo_smart_wi_fi_power_strip"])
@pytest.mark.parametrize("attributes", [TAPO_STRIP_NUMBER_TAG_ATTRIBUTES])
async def test_power_topology_entities_rediscovered_when_outlet_gone(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test measurement entities return on the node device when their outlet is gone.

    The outlet's child device is pruned with the measurement entities, which are
    then rediscovered in the same node setup.
    """
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    parent = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, matter_node, 0), entry_id
    )
    assert parent is not None

    matter_node.endpoints.pop(2)
    fire_node_updated_event(matter_client, matter_node)
    await hass.async_block_till_done()

    power_entry = entity_registry.async_get(
        "sensor.smart_wi_fi_power_strip_channel_2_power"
    )
    assert power_entry is not None
    assert power_entry.device_id == parent.id


@pytest.mark.parametrize("node_fixture", ["tapo_smart_wi_fi_power_strip"])
@pytest.mark.parametrize("attributes", [TAPO_STRIP_NUMBER_TAG_ATTRIBUTES])
async def test_power_topology_entities_follow_collapsed_child(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test measurement entities move back to the node device with their outlet."""
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    parent = device_registry.async_get_device_by_identifier(
        identifier_for(matter_client, matter_node, 0), entry_id
    )
    assert parent is not None

    # Drop the other outlets so outlet 1 no longer splits.
    for endpoint_id in range(2, 7):
        matter_node.endpoints.pop(endpoint_id)
    fire_node_updated_event(matter_client, matter_node)
    await hass.async_block_till_done()

    assert not dr.async_entries_for_parent_device(device_registry, parent.id)
    for entity_id in (TAPO_STRIP_SWITCH_1, TAPO_STRIP_POWER_1):
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry is not None
        assert entity_entry.device_id == parent.id


@pytest.mark.parametrize("node_fixture", ["tapo_smart_wi_fi_power_strip"])
@pytest.mark.parametrize("attributes", [TAPO_STRIP_NUMBER_TAG_ATTRIBUTES])
async def test_power_topology_entities_renamed_when_outlet_removed(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test measurement entities moved off a removed outlet's child are renamed.

    They were created on the child device without a name suffix, so the entry is
    reloaded to recreate them with the suffixes of the node device.
    """
    for endpoint_id in (1, 2):
        remove_endpoint(matter_client, matter_node, endpoint_id)
        fire_node_updated_event(matter_client, matter_node)
        await hass.async_block_till_done()

    for entity_id, name in (
        (TAPO_STRIP_POWER_1, "Smart Wi-Fi Power Strip Power (7)"),
        (
            "sensor.smart_wi_fi_power_strip_channel_2_power",
            "Smart Wi-Fi Power Strip Power (8)",
        ),
    ):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.name == name


@pytest.mark.parametrize("node_fixture", ["eve_energy_20ecn4101"])
async def test_collapsed_endpoint_entities_renamed(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test the entities of an endpoint that stops splitting get its label."""
    remove_endpoint(matter_client, matter_node, 1)
    fire_node_updated_event(matter_client, matter_node)
    await hass.async_block_till_done()

    state = hass.states.get("select.eve_energy_20ecn4101_bottom_power_on_behavior")
    assert state is not None
    assert state.name == "Eve Energy 20ECN4101 Power-on behavior (bottom)"


@pytest.mark.parametrize("node_fixture", ["tapo_smart_wi_fi_power_strip"])
@pytest.mark.parametrize("attributes", [TAPO_STRIP_NUMBER_TAG_ATTRIBUTES])
async def test_power_topology_outlet_readded_before_node_update(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test measurement entities return to an outlet that comes back at once.

    The server sends one node update for both changes, and ENDPOINT_ADDED after
    it, so the node update already has the outlet again.
    """
    remove_endpoint(matter_client, matter_node, 1)
    matter_node.update(matter_node.node_data)
    fire_node_updated_event(matter_client, matter_node)
    fire_endpoint_event(matter_client, EventType.ENDPOINT_ADDED, matter_node, 1)
    await hass.async_block_till_done()

    switch_entry = entity_registry.async_get(TAPO_STRIP_SWITCH_1)
    assert switch_entry is not None
    power_entry = entity_registry.async_get(TAPO_STRIP_POWER_1)
    assert power_entry is not None
    assert power_entry.device_id == switch_entry.device_id


@pytest.mark.parametrize("node_fixture", ["tapo_smart_wi_fi_power_strip"])
@pytest.mark.parametrize("attributes", [TAPO_STRIP_NUMBER_TAG_ATTRIBUTES])
async def test_power_topology_disabled_entities_moved_dont_reload(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test moving only disabled measurement entities off an outlet doesn't reload."""
    unique_id_prefix = (
        f"{get_device_id(matter_client.server_info, matter_node.endpoints[7])}-7-"
    )
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    for entity_entry in er.async_entries_for_config_entry(entity_registry, entry_id):
        if entity_entry.unique_id.startswith(unique_id_prefix):
            entity_registry.async_update_entity(
                entity_entry.entity_id, disabled_by=er.RegistryEntryDisabler.USER
            )

    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        remove_endpoint(matter_client, matter_node, 1)
        fire_node_updated_event(matter_client, matter_node)
        await hass.async_block_till_done()

    mock_reload.assert_not_called()
    power_entry = entity_registry.async_get(TAPO_STRIP_POWER_1)
    assert power_entry is not None
    assert power_entry.disabled_by is er.RegistryEntryDisabler.USER


@pytest.mark.parametrize("node_fixture", ["tapo_smart_wi_fi_power_strip"])
@pytest.mark.parametrize("attributes", [TAPO_STRIP_NUMBER_TAG_ATTRIBUTES])
async def test_power_topology_outlet_removed_with_measurement_endpoint(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test removing an outlet with its measurement endpoint doesn't reload."""
    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        for endpoint_id in (1, 7):
            remove_endpoint(matter_client, matter_node, endpoint_id)
        fire_node_updated_event(matter_client, matter_node)
        await hass.async_block_till_done()

    mock_reload.assert_not_called()
    assert entity_registry.async_get(TAPO_STRIP_SWITCH_1) is None
    assert entity_registry.async_get(TAPO_STRIP_POWER_1) is None


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


@pytest.mark.parametrize("node_fixture", ["mock_composed_bridge"])
@pytest.mark.parametrize(
    "removed_endpoint_ids",
    [
        pytest.param((4, 3, 2), id="parts_first"),
        pytest.param((2,), id="parent_only"),
    ],
)
async def test_bridged_device_readded_after_removal(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_registry: er.EntityRegistry,
    removed_endpoint_ids: tuple[int, ...],
) -> None:
    """Test a bridged device's entities are rediscovered after remove and re-add.

    The server announces the removal of the parts before their parent's.
    """
    for endpoint_id in removed_endpoint_ids:
        remove_endpoint(matter_client, matter_node, endpoint_id)
    fire_node_updated_event(matter_client, matter_node)
    await hass.async_block_till_done()
    assert entity_registry.async_get("switch.kitchen_plug") is None
    assert entity_registry.async_get("sensor.kitchen_plug_temperature") is None

    matter_node.update(matter_node.node_data)
    fire_node_updated_event(matter_client, matter_node)
    for endpoint_id in (2, 3, 4):
        fire_endpoint_event(
            matter_client, EventType.ENDPOINT_ADDED, matter_node, endpoint_id
        )
    await hass.async_block_till_done()

    assert entity_registry.async_get("switch.kitchen_plug") is not None
    assert entity_registry.async_get("sensor.kitchen_plug_temperature") is not None


@pytest.mark.parametrize("node_fixture", ["mock_composed_bridge"])
async def test_bridged_device_part_removed_and_readded(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a part of a bridged device is removed and re-added on its own."""
    remove_endpoint(matter_client, matter_node, 3)
    fire_node_updated_event(matter_client, matter_node)
    await hass.async_block_till_done()
    assert entity_registry.async_get("switch.kitchen_plug") is None
    assert entity_registry.async_get("sensor.kitchen_plug_temperature") is not None

    matter_node.update(matter_node.node_data)
    fire_node_updated_event(matter_client, matter_node)
    fire_endpoint_event(matter_client, EventType.ENDPOINT_ADDED, matter_node, 3)
    await hass.async_block_till_done()

    assert entity_registry.async_get("switch.kitchen_plug") is not None
    assert "does not generate unique IDs" not in caplog.text


@pytest.mark.parametrize("node_fixture", ["mock_composed_bridge"])
@pytest.mark.parametrize("attributes", [{"3/29/3": [4]}])
async def test_bridged_device_nested_part_readded_after_removal(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a part below another part is rediscovered after remove and re-add.

    Here the part is announced before its own part, which the client then drops
    with it.
    """
    assert matter_node.get_closest_compose_parent(4) == matter_node.endpoints[3]
    for endpoint_id in (3, 4, 2):
        remove_endpoint(matter_client, matter_node, endpoint_id)
    fire_node_updated_event(matter_client, matter_node)
    await hass.async_block_till_done()
    assert entity_registry.async_get("sensor.kitchen_plug_temperature") is None

    matter_node.update(matter_node.node_data)
    fire_node_updated_event(matter_client, matter_node)
    for endpoint_id in (2, 3, 4):
        fire_endpoint_event(
            matter_client, EventType.ENDPOINT_ADDED, matter_node, endpoint_id
        )
    await hass.async_block_till_done()

    assert entity_registry.async_get("switch.kitchen_plug") is not None
    assert entity_registry.async_get("sensor.kitchen_plug_temperature") is not None


@pytest.mark.parametrize("node_fixture", ["mock_air_purifier"])
async def test_composed_parts_removed_before_parent(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the parts of a composed device are removed when announced first."""
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    for endpoint_id in (2, 3, 4, 5, 1):
        remove_endpoint(matter_client, matter_node, endpoint_id)
    fire_node_updated_event(matter_client, matter_node)
    await hass.async_block_till_done()

    assert entity_registry.async_get("climate.mock_air_purifier") is None
    assert entity_registry.async_get("sensor.mock_air_purifier_temperature") is None
    # Only the root endpoint's entities are left.
    root_prefix = (
        f"{get_device_id(matter_client.server_info, matter_node.endpoints[0])}-0-"
    )
    for entity_entry in er.async_entries_for_config_entry(entity_registry, entry_id):
        assert entity_entry.unique_id.startswith(root_prefix)
    assert entity_registry.async_get("update.mock_air_purifier_firmware") is not None


async def test_migrate_unique_id_for_part_nested_below_another_part(
    hass: HomeAssistant,
    matter_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the unique_id of a part nested below another part is migrated.

    `get_compose_parent()` resolves to the top of a composition instead of the
    closest parent, so a part nested below another part of a bridge (here,
    endpoint 4 nested below endpoint 3, itself below the `BridgedNode` endpoint 2)
    gets a `-2-4-` unique_id postfix instead of the `-MatterNodeDevice-4-` postfix
    it got before. An existing entity registry entry using the old unique_id must
    be renamed to the new one so it is not orphaned.
    """
    node = create_node_from_fixture("mock_composed_bridge", {"3/29/3": [4]})
    matter_client.get_nodes.return_value = [node]
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={"url": "ws://localhost:5580/ws"}
    )
    config_entry.add_to_hass(hass)

    legacy_entry = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "00000000000004D2-0000000000000063-MatterNodeDevice-4-TemperatureSensor-1026-0",
        config_entry=config_entry,
        suggested_object_id="nested_part_temperature",
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    migrated_entry = entity_registry.async_get(legacy_entry.entity_id)
    assert migrated_entry is not None
    assert (
        migrated_entry.unique_id
        == "00000000000004D2-0000000000000063-2-4-TemperatureSensor-1026-0"
    )
    assert hass.states.get(legacy_entry.entity_id) is not None


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
