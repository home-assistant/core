"""Test Matter entity behavior."""

import copy
from typing import Any
from unittest.mock import MagicMock

from matter_server.client.models.node import MatterNode
from matter_server.common.models import EventType
import pytest

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    _setup_integration_with_nodes,
    create_node_from_fixture,
    set_node_attribute,
    set_node_attribute_and_notify,
    setup_integration_with_node_fixture,
    trigger_subscription_callback,
)


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize(
    ("node_fixture", "entity_id", "expected_translation_key", "expected_name"),
    [
        ("mock_onoff_light", "light.mock_onoff_light", "light", "Mock OnOff Light"),
        ("mock_door_lock", "lock.mock_door_lock", "lock", "Mock Door Lock"),
        ("mock_thermostat", "climate.mock_thermostat", "thermostat", "Mock Thermostat"),
        ("mock_valve", "valve.mock_valve", "valve", "Mock Valve"),
        ("mock_fan", "fan.mocked_fan_switch", "fan", "Mocked Fan Switch"),
        ("eve_energy_plug", "switch.eve_energy_plug", "switch", "Eve Energy Plug"),
        ("mock_vacuum_cleaner", "vacuum.mock_vacuum", "vacuum", "Mock Vacuum"),
        (
            "silabs_water_heater",
            "water_heater.water_heater",
            "water_heater",
            "Water Heater",
        ),
    ],
)
async def test_single_endpoint_platform_translation_key(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entity_id: str,
    expected_translation_key: str,
    expected_name: str,
) -> None:
    """Test single-endpoint entities on platforms with _platform_translation_key.

    The translation key must always be present for state_attributes translations
    and icon translations. When there is no endpoint postfix, the entity name
    should be suppressed (None) so only the device name is displayed.
    """
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.translation_key == expected_translation_key
    # No original_name means the entity name is suppressed,
    # so only the device name is shown
    assert entry.original_name is None

    state = hass.states.get(entity_id)
    assert state is not None
    # The friendly name should be just the device name (no entity name appended)
    assert state.name == expected_name


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["inovelli_vtm31"])
async def test_multi_endpoint_entity_translation_key(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that multi-endpoint entities have a translation key and a name postfix.

    When a device has the same primary attribute on multiple endpoints,
    the entity name gets postfixed with the endpoint ID. The translation key
    must still always be set for translations.
    """
    # Endpoint 1
    entry_1 = entity_registry.async_get("light.inovelli_light_1")
    assert entry_1 is not None
    assert entry_1.translation_key == "light"
    assert entry_1.original_name == "Light (1)"

    state_1 = hass.states.get("light.inovelli_light_1")
    assert state_1 is not None
    assert state_1.name == "Inovelli Light (1)"

    # Endpoint 6
    entry_6 = entity_registry.async_get("light.inovelli_light_6")
    assert entry_6 is not None
    assert entry_6.translation_key == "light"
    assert entry_6.original_name == "Light (6)"

    state_6 = hass.states.get("light.inovelli_light_6")
    assert state_6 is not None
    assert state_6.name == "Inovelli Light (6)"


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["eve_energy_20ecn4101"])
async def test_label_modified_entity_translation_key(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that label-modified entities have a translation key and a label postfix.

    When a device uses Matter labels to differentiate endpoints,
    the entity name gets the label as a postfix. The translation key
    must still always be set for translations.
    """
    # Top outlet
    entry_top = entity_registry.async_get("switch.eve_energy_20ecn4101_switch_top")
    assert entry_top is not None
    assert entry_top.translation_key == "switch"
    assert entry_top.original_name == "Switch (top)"

    state_top = hass.states.get("switch.eve_energy_20ecn4101_switch_top")
    assert state_top is not None
    assert state_top.name == "Eve Energy 20ECN4101 Switch (top)"

    # Bottom outlet
    entry_bottom = entity_registry.async_get(
        "switch.eve_energy_20ecn4101_switch_bottom"
    )
    assert entry_bottom is not None
    assert entry_bottom.translation_key == "switch"
    assert entry_bottom.original_name == "Switch (bottom)"

    state_bottom = hass.states.get("switch.eve_energy_20ecn4101_switch_bottom")
    assert state_bottom is not None
    assert state_bottom.name == "Eve Energy 20ECN4101 Switch (bottom)"


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["eve_thermo_v4"])
async def test_description_translation_key_not_overridden(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a description-level translation key is not overridden.

    When an entity description already sets translation_key (e.g. "child_lock"),
    the _platform_translation_key logic should not override it. The entity keeps
    its description-level translation key and name.
    """
    entry = entity_registry.async_get("switch.eve_thermo_20ebp1701_child_lock")
    assert entry is not None
    # The description-level translation key should be preserved, not overridden
    # by _platform_translation_key ("switch")
    assert entry.translation_key == "child_lock"
    assert entry.original_name == "Child lock"

    state = hass.states.get("switch.eve_thermo_20ebp1701_child_lock")
    assert state is not None
    assert state.name == "Eve Thermo 20EBP1701 Child lock"


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["air_quality_sensor"])
async def test_entity_name_from_description_translation_key(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entity name derived from an explicit description translation key.

    Sensor entities do not set _platform_translation_key on the platform class.
    When the entity description sets translation_key explicitly, the entity name
    is derived from that translation key.
    """
    entry = entity_registry.async_get(
        "sensor.lightfi_aq1_air_quality_sensor_air_quality"
    )
    assert entry is not None
    assert entry.translation_key == "air_quality"
    assert entry.original_name == "Air quality"

    state = hass.states.get("sensor.lightfi_aq1_air_quality_sensor_air_quality")
    assert state is not None
    assert state.name == "lightfi-aq1-air-quality-sensor Air quality"


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["mock_temperature_sensor"])
async def test_entity_name_from_device_class(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entity name derived from device class when no translation key is set.

    Sensor entities do not set _platform_translation_key on the platform class.
    When the entity description also has no translation_key, the entity name
    is derived from the device class instead.
    """
    entry = entity_registry.async_get("sensor.mock_temperature_sensor_temperature")
    assert entry is not None
    assert entry.translation_key is None
    # Name is derived from the device class
    assert entry.original_name == "Temperature"

    state = hass.states.get("sensor.mock_temperature_sensor_temperature")
    assert state is not None
    assert state.name == "Mock Temperature Sensor Temperature"


# ---------------------------------------------------------------------------
# Tests for _get_bridged_reachable(), availability initialisation and
# BridgedDeviceBasicInformation.Reachable subscription logic.
#
# Fixture used for bridge tests: "atios_knx_bridge" (node_id=62,
# is_bridge=True).  Endpoint 29 carries the BridgedDeviceBasicInformation
# cluster (57) with the Reachable attribute (attribute_id=17, path "29/57/17")
# and exposes an electrical-power sensor entity.
#
# Entity used as proxy: sensor.electricity_monitor_ac_power
# ---------------------------------------------------------------------------

_BRIDGE_ENTITY_ID = "sensor.electricity_monitor_ac_power"
# AttributePath for BridgedDeviceBasicInformation.Reachable on endpoint 29.
# create_attribute_path(29, 57, 17) == "29/57/17"
_REACHABLE_ATTR_PATH = "29/57/17"


async def test_bridged_entity_unavailable_when_reachable_false_at_startup(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Test Entity.available is False when Reachable attribute is False.

    When BridgedDeviceBasicInformation.Reachable is False the entity must be
    unavailable from the moment it is created, even though the node itself is
    online.
    """
    await setup_integration_with_node_fixture(
        hass,
        "atios_knx_bridge",
        matter_client,
        # Override: Reachable = False at fixture load time.
        {_REACHABLE_ATTR_PATH: False},
    )

    state = hass.states.get(_BRIDGE_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_bridged_entity_becomes_unavailable_on_reachable_false(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Test entity becomes unavailable when Reachable attribute changes to False.

    Sequence:
    1. Setup with Reachable=True  → entity available.
    2. Set Reachable=False via set_node_attribute.
    3. Fire ATTRIBUTE_UPDATED event              → entity must become unavailable.
    """
    matter_node = await setup_integration_with_node_fixture(
        hass, "atios_knx_bridge", matter_client
    )

    state = hass.states.get(_BRIDGE_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    # Simulate the bridge reporting the endpoint as unreachable.
    await set_node_attribute_and_notify(
        hass,
        matter_client,
        matter_node,
        endpoint=29,
        cluster_id=57,
        attribute_id=17,
        value=False,
    )

    state = hass.states.get(_BRIDGE_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_bridged_entity_recovers_when_reachable_true(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Test entity becomes available again when Reachable attribute returns to True.

    Sequence:
    1. Setup with Reachable=False → entity unavailable.
    2. Set Reachable=True via set_node_attribute.
    3. Fire ATTRIBUTE_UPDATED event              → entity must become available.
    """
    matter_node = await setup_integration_with_node_fixture(
        hass,
        "atios_knx_bridge",
        matter_client,
        {_REACHABLE_ATTR_PATH: False},
    )

    state = hass.states.get(_BRIDGE_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Simulate the bridge reporting the endpoint as reachable again.
    await set_node_attribute_and_notify(
        hass,
        matter_client,
        matter_node,
        endpoint=29,
        cluster_id=57,
        attribute_id=17,
        value=True,
    )

    state = hass.states.get(_BRIDGE_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_bridged_entity_unavailable_when_node_goes_offline(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Test entity becomes unavailable when the bridge node goes offline.

    Even if BridgedDeviceBasicInformation.Reachable is True, the entity must
    become unavailable when node.available is False, because Entity.available
    is computed as node.available AND BridgedDeviceBasicInformation.Reachable.
    """
    matter_node = await setup_integration_with_node_fixture(
        hass, "atios_knx_bridge", matter_client
    )

    state = hass.states.get(_BRIDGE_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    # Take the whole node offline.
    matter_node.node_data.available = False
    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_UPDATED, data=matter_node
    )

    state = hass.states.get(_BRIDGE_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Bring the node back online.
    matter_node.node_data.available = True
    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_UPDATED, data=matter_node
    )

    state = hass.states.get(_BRIDGE_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["mock_onoff_light"])
async def test_non_bridged_entity_availability_tracks_node(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test non-bridged entity availability tracks node.available only.

    For an endpoint without BridgedDeviceBasicInformation.Reachable,
    Entity.available equals node.available.
    """
    entity_id = "light.mock_onoff_light"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    # Take the node offline.
    matter_node.node_data.available = False
    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_UPDATED, data=matter_node
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Bring the node back online.
    matter_node.node_data.available = True
    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_UPDATED, data=matter_node
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_bridged_entity_subscribes_to_reachable_attribute(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Test that Entity subscribes to BridgedDeviceBasicInformation.Reachable.

    When an endpoint has the BridgedDeviceBasicInformation.Reachable attribute
    (i.e. has_attribute returns True), the entity must create an
    ATTRIBUTE_UPDATED subscription for that attribute path so that reachability
    changes trigger the matter event callback and update Entity.available.
    """
    await setup_integration_with_node_fixture(hass, "atios_knx_bridge", matter_client)

    subscribe_calls = matter_client.subscribe_events.call_args_list
    assert any(
        call.kwargs.get("attr_path_filter") == _REACHABLE_ATTR_PATH
        and call.kwargs.get("event_filter") == EventType.ATTRIBUTE_UPDATED
        for call in subscribe_calls
    ), (
        "Expected a subscribe_events call with attr_path_filter="
        f"{_REACHABLE_ATTR_PATH!r} and event_filter=ATTRIBUTE_UPDATED,"
        " but none was found."
    )


@pytest.mark.usefixtures("matter_node")
@pytest.mark.parametrize("node_fixture", ["mock_onoff_light"])
async def test_non_bridged_entity_does_not_subscribe_to_reachable(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test that Entity does NOT subscribe to Reachable for non-bridge.

    For an endpoint without BridgedDeviceBasicInformation.Reachable, no extra
    subscription must be created for attribute path "*/57/17".
    """
    subscribe_calls = matter_client.subscribe_events.call_args_list
    # Endpoint 1 of mock_onoff_light has no cluster 57 at all.
    # No subscription to any "*/57/17" path should exist.
    assert not any(
        isinstance(call.kwargs.get("attr_path_filter"), str)
        and "/57/17" in call.kwargs["attr_path_filter"]
        for call in subscribe_calls
    ), (
        "Unexpected subscribe_events call for"
        " BridgedDeviceBasicInformation.Reachable"
        " on a non-bridged entity."
    )


# ---------------------------------------------------------------------------
# Tests for composed devices with parent Reachable attribute.
#
# Fixture used for composed device tests: "fritz_bridge" (node_id=1,
# is_bridge=True). This fixture has composed devices where endpoint 40 is
# a composed device under endpoint 42's PartsList, carrying the
# BridgedDeviceBasicInformation cluster (57) with the Reachable attribute
# (attribute_id=17) on the parent endpoint 42.
#
# Entity used as proxy: switch.my_device (on endpoint 40)
# Parent Reachable path: "42/57/17" (on endpoint 42)
# ---------------------------------------------------------------------------

_COMPOSED_ENTITY_ID = "switch.my_device"
# AttributePath for BridgedDeviceBasicInformation.Reachable on parent endpoint 42.
_COMPOSED_PARENT_REACHABLE_ATTR_PATH = "42/57/17"


async def test_composed_entity_state_updates_when_parent_reachable_changes(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Test composed entity becomes (un-)available when parent Reachable changes.

    Sequence:
    1. Setup with parent Reachable=False → entity unavailable.
    2. Set parent Reachable=True via set_node_attribute.
    3. Fire ATTRIBUTE_UPDATED event → entity must become available.
    4. Set parent Reachable=False via set_node_attribute.
    5. Fire ATTRIBUTE_UPDATED event → entity must become unavailable.
    """
    matter_node = await setup_integration_with_node_fixture(
        hass, "fritz_bridge", matter_client
    )

    state = hass.states.get(_COMPOSED_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Simulate the parent endpoint reporting as reachable again.
    await set_node_attribute_and_notify(
        hass,
        matter_client,
        matter_node,
        endpoint=42,
        cluster_id=57,
        attribute_id=17,
        value=True,
    )

    state = hass.states.get(_COMPOSED_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    # Simulate the parent endpoint reporting as unreachable again.
    await set_node_attribute_and_notify(
        hass,
        matter_client,
        matter_node,
        endpoint=42,
        cluster_id=57,
        attribute_id=17,
        value=False,
    )

    state = hass.states.get(_COMPOSED_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_composed_entity_unavailable_when_parent_node_goes_offline(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Test composed entity becomes unavailable when the bridge node goes offline.

    Even if parent BridgedDeviceBasicInformation.Reachable is True, the composed
    entity must become unavailable when node.available is False, because
    Entity.available is computed as node.available AND parent Reachable.
    """
    matter_node = await setup_integration_with_node_fixture(
        hass,
        "fritz_bridge",
        matter_client,
        # fake as reachable at startup so we can test the node
        # going offline while reachable
        {_COMPOSED_PARENT_REACHABLE_ATTR_PATH: True},
    )

    state = hass.states.get(_COMPOSED_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    # Take the whole node offline.
    matter_node.node_data.available = False
    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_UPDATED, data=matter_node
    )

    state = hass.states.get(_COMPOSED_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Bring the node back online.
    matter_node.node_data.available = True
    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_UPDATED, data=matter_node
    )

    state = hass.states.get(_COMPOSED_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_composed_entity_subscribes_to_parent_reachable_attribute(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Test composed entity subscribes to parent Reachable.

    When an endpoint belongs to a composed device, the BridgedDeviceBasicInformation
    cluster lives on the parent endpoint. The entity must create an ATTRIBUTE_UPDATED
    subscription for the parent's Reachable attribute path so that reachability
    changes on the parent trigger the matter event callback and update Entity.available.
    """
    await setup_integration_with_node_fixture(hass, "fritz_bridge", matter_client)

    subscribe_calls = matter_client.subscribe_events.call_args_list
    assert any(
        call.kwargs.get("attr_path_filter") == _COMPOSED_PARENT_REACHABLE_ATTR_PATH
        and call.kwargs.get("event_filter") == EventType.ATTRIBUTE_UPDATED
        for call in subscribe_calls
    ), (
        "Expected a subscribe_events call with attr_path_filter="
        f"{_COMPOSED_PARENT_REACHABLE_ATTR_PATH!r}"
        " and event_filter=ATTRIBUTE_UPDATED, but none was found."
    )


@pytest.mark.parametrize(
    ("node_fixture", "entity_id", "expected_event_filters"),
    [
        pytest.param(
            "mock_onoff_light",
            "light.mock_onoff_light",
            {EventType.ATTRIBUTE_UPDATED, EventType.NODE_UPDATED},
            id="base_entity",
        ),
        pytest.param(
            "mock_generic_switch",
            "event.mock_generic_switch_button",
            {EventType.ATTRIBUTE_UPDATED, EventType.NODE_UPDATED, EventType.NODE_EVENT},
            id="event",
        ),
        pytest.param(
            "mock_door_lock",
            "lock.mock_door_lock",
            {EventType.ATTRIBUTE_UPDATED, EventType.NODE_UPDATED, EventType.NODE_EVENT},
            id="lock",
        ),
    ],
)
async def test_entity_removal_unsubscribes_events(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    node_fixture: str,
    entity_id: str,
    expected_event_filters: set[EventType],
) -> None:
    """Test removing an entity unsubscribes all its Matter client subscriptions."""
    subscriptions: list[tuple[dict[str, Any], MagicMock]] = []

    def _subscribe_events(**kwargs: Any) -> MagicMock:
        unsubscribe = MagicMock()
        subscriptions.append((kwargs, unsubscribe))
        return unsubscribe

    matter_client.subscribe_events.side_effect = _subscribe_events
    await setup_integration_with_node_fixture(hass, node_fixture, matter_client)

    entity_subscriptions = [
        (kwargs["event_filter"], unsubscribe)
        for kwargs, unsubscribe in subscriptions
        # Only bound entity methods have an entity_id; other callbacks are skipped.
        if getattr(getattr(kwargs["callback"], "__self__", None), "entity_id", None)
        == entity_id
    ]
    assert {event_filter for event_filter, _ in entity_subscriptions} == (
        expected_event_filters
    )
    assert not any(unsubscribe.called for _, unsubscribe in entity_subscriptions)

    entity_registry.async_remove(entity_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id) is None
    assert all(unsubscribe.called for _, unsubscribe in entity_subscriptions)


async def _remove_attributes(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    paths: list[str],
) -> None:
    """Remove attributes the way the server reports it.

    Each attribute is first sent as a null value, then a node_updated without the
    attribute follows.
    """
    for path in paths:
        endpoint, cluster, attribute = (int(part) for part in path.split("/"))
        await set_node_attribute_and_notify(
            hass,
            matter_client,
            matter_node,
            endpoint=endpoint,
            cluster_id=cluster,
            attribute_id=attribute,
            value=None,
        )
    node_data = copy.deepcopy(matter_node.node_data)
    for path in paths:
        del node_data.attributes[path]
    matter_node.update(node_data)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_UPDATED,
        matter_node,
        node_id=matter_node.node_id,
    )


@pytest.mark.parametrize(
    ("node_fixture", "entity_id", "removed_paths"),
    [
        (
            "aqara_door_window_p2",
            "number.aqara_door_and_window_sensor_p2_sensitivity",
            ["1/128/0", "1/128/1"],
        ),
        (
            "aqara_thermostat_w500",
            "number.floor_heating_thermostat_occupied_setback",
            ["1/513/52", "1/513/53", "1/513/54"],
        ),
        (
            "mock_oven",
            "number.mock_oven_temperature_setpoint",
            ["2/86/0", "2/86/1", "2/86/2"],
        ),
        ("mock_oven", "select.mock_oven_temperature_level", ["4/86/4", "4/86/5"]),
        (
            "silabs_laundrywasher",
            "select.laundrywasher_spin_speed",
            ["1/83/0", "1/83/1"],
        ),
        (
            "silabs_laundrywasher",
            "select.laundrywasher_number_of_rinses",
            ["1/83/2", "1/83/3"],
        ),
        (
            "mock_microwave_oven",
            "select.mock_microwave_oven_power_level_w",
            ["1/95/6", "1/95/7"],
        ),
    ],
)
async def test_entity_removed_with_required_attribute(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
    removed_paths: list[str],
) -> None:
    """Test an entity is removed when the device removes a required attribute."""
    assert hass.states.get(entity_id) is not None

    await _remove_attributes(hass, matter_client, matter_node, removed_paths)

    assert entity_registry.async_get(entity_id) is None
    assert hass.states.get(entity_id) is None


@pytest.mark.parametrize("node_fixture", ["silabs_laundrywasher"])
async def test_entity_added_again_with_required_attribute(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test an entity removed with a required attribute comes back with it."""
    entity_id = "select.laundrywasher_spin_speed"
    removed_paths = ["1/83/0", "1/83/1"]
    old_values = {
        path: matter_node.node_data.attributes[path] for path in removed_paths
    }

    await _remove_attributes(hass, matter_client, matter_node, removed_paths)
    assert entity_registry.async_get(entity_id) is None

    for path, value in old_values.items():
        endpoint, cluster, attribute = (int(part) for part in path.split("/"))
        matter_node.node_data.attributes[path] = value
        set_node_attribute(matter_node, endpoint, cluster, attribute, value)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_UPDATED,
        matter_node,
        node_id=matter_node.node_id,
    )

    assert entity_registry.async_get(entity_id) is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "Off"


@pytest.mark.parametrize(
    ("node_fixture", "entity_id", "path"),
    [
        # null when the current mode has no spin speed
        ("silabs_laundrywasher", "select.laundrywasher_spin_speed", "1/83/1"),
        # null when the device presents no phases
        ("silabs_laundrywasher", "sensor.laundrywasher_current_phase", "1/96/0"),
        ("silabs_laundrywasher", "sensor.laundrywasher_current_phase", "1/96/1"),
    ],
)
async def test_null_list_index(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
    path: str,
) -> None:
    """Test a null list or list index leaves the entity state unknown."""
    endpoint, cluster, attribute = (int(part) for part in path.split("/"))
    await set_node_attribute_and_notify(
        hass,
        matter_client,
        matter_node,
        endpoint=endpoint,
        cluster_id=cluster,
        attribute_id=attribute,
        value=None,
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unknown"


@pytest.mark.parametrize(
    ("node_fixture", "entity_id", "updates", "check_attribute"),
    [
        ("silabs_fan", "fan.sl_fan", [("1/514/10", None)], "preset_mode"),
        (
            "extended_color_light",
            "light.mock_extended_color_light",
            [("1/768/0", None)],
            "hs_color",
        ),
        (
            "extended_color_light",
            "light.mock_extended_color_light",
            [("1/768/8", 1), ("1/768/3", None)],
            "xy_color",
        ),
    ],
)
async def test_null_optional_attribute(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
    updates: list[tuple[str, Any]],
    check_attribute: str,
) -> None:
    """Test a null optional attribute leaves the derived state empty."""
    for path, value in updates:
        endpoint, cluster, attribute = (int(part) for part in path.split("/"))
        await set_node_attribute_and_notify(
            hass,
            matter_client,
            matter_node,
            endpoint=endpoint,
            cluster_id=cluster,
            attribute_id=attribute,
            value=value,
        )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"
    assert check_attribute in state.attributes
    if check_attribute != "preset_mode":
        assert state.attributes[check_attribute] is None


@pytest.mark.parametrize("node_fixture", ["silabs_laundrywasher"])
async def test_entities_removed_in_one_node_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    node_fixture: str,
) -> None:
    """Test all entities that lose a required attribute in one update are removed.

    Like the client, the subscribers are called from the list that removing an
    entity unsubscribes it from.
    """
    subscribers: dict[str, list[Any]] = {}

    def _subscribe_events(**kwargs: Any) -> Any:
        key = (
            f"{kwargs.get('event_filter')}/{kwargs.get('node_filter')}/"
            f"{kwargs.get('attr_path_filter')}"
        )
        subscribers.setdefault(key, []).append(kwargs["callback"])
        return lambda: subscribers[key].remove(kwargs["callback"])

    matter_client.subscribe_events.side_effect = _subscribe_events
    node = await setup_integration_with_node_fixture(hass, node_fixture, matter_client)
    removed = {
        "select.laundrywasher_spin_speed": ["1/83/0", "1/83/1"],
        "select.laundrywasher_number_of_rinses": ["1/83/2", "1/83/3"],
    }

    node_data = copy.deepcopy(node.node_data)
    for paths in removed.values():
        for path in paths:
            del node_data.attributes[path]
    node.update(node_data)
    for callback in subscribers[f"{EventType.NODE_UPDATED}/{node.node_id}/None"]:
        callback(EventType.NODE_UPDATED, node)
    await hass.async_block_till_done()

    for entity_id in removed:
        assert entity_registry.async_get(entity_id) is None


@pytest.mark.parametrize("node_fixture", ["silabs_laundrywasher"])
async def test_entity_kept_when_endpoint_leaves_node_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test entities of an endpoint missing from the node data are not removed.

    The endpoint is removed with its device when endpoint_removed arrives.
    """
    entity_id = "select.laundrywasher_spin_speed"
    node_data = copy.deepcopy(matter_node.node_data)
    node_data.attributes = {
        path: value
        for path, value in node_data.attributes.items()
        if not path.startswith("1/")
    }
    matter_node.update(node_data)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_UPDATED,
        matter_node,
        node_id=matter_node.node_id,
    )

    assert entity_registry.async_get(entity_id) is not None


def _dispatch(
    matter_client: MagicMock, event: EventType, data: Any, path: str | None
) -> None:
    """Call the matching subscribers without running the event loop."""
    for sub in matter_client.subscribe_events.call_args_list:
        kwargs = sub.kwargs
        if kwargs.get("event_filter") != event:
            continue
        if path is not None and kwargs.get("attr_path_filter") != path:
            continue
        kwargs["callback"](event, data)


@pytest.mark.parametrize("node_fixture", ["silabs_laundrywasher"])
async def test_entity_kept_when_attribute_comes_back_in_same_batch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test an entity is kept when a later update of the same batch restores it."""
    entity_id = "select.laundrywasher_spin_speed"
    full = copy.deepcopy(matter_node.node_data)
    partial = copy.deepcopy(full)
    for path in ("1/83/0", "1/83/1"):
        del partial.attributes[path]

    matter_node.update(partial)
    _dispatch(matter_client, EventType.NODE_UPDATED, matter_node, None)
    matter_node.update(full)
    _dispatch(matter_client, EventType.NODE_UPDATED, matter_node, None)
    await hass.async_block_till_done()

    assert entity_registry.async_get(entity_id) is not None


@pytest.mark.parametrize("node_fixture", ["aqara_door_window_p2"])
async def test_entity_kept_when_feature_comes_back_in_same_batch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test an entity is kept when its feature leaves and returns in one batch."""
    entity_id = "number.aqara_door_and_window_sensor_p2_sensitivity"
    path = "1/128/65532"
    feature_map = matter_node.node_data.attributes[path]

    for value in (0, feature_map):
        set_node_attribute(matter_node, 1, 128, 65532, value)
        _dispatch(matter_client, EventType.ATTRIBUTE_UPDATED, value, path)
    await hass.async_block_till_done()

    assert entity_registry.async_get(entity_id) is not None

    set_node_attribute(matter_node, 1, 128, 65532, 0)
    _dispatch(matter_client, EventType.ATTRIBUTE_UPDATED, 0, path)
    await hass.async_block_till_done()

    assert entity_registry.async_get(entity_id) is None


@pytest.mark.parametrize("node_fixture", ["aqara_door_window_p2"])
async def test_entity_removed_for_other_reason_in_same_batch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test a returning feature does not keep an entity missing a required attribute."""
    entity_id = "number.aqara_door_and_window_sensor_p2_sensitivity"
    node_data = copy.deepcopy(matter_node.node_data)
    del node_data.attributes["1/128/0"]

    set_node_attribute(matter_node, 1, 128, 65532, 0)
    _dispatch(matter_client, EventType.ATTRIBUTE_UPDATED, 0, "1/128/65532")
    matter_node.update(node_data)
    _dispatch(matter_client, EventType.NODE_UPDATED, matter_node, None)
    await hass.async_block_till_done()

    assert entity_registry.async_get(entity_id) is None


@pytest.mark.parametrize("node_fixture", ["silabs_fan"])
async def test_node_update_without_wind_setting(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test a fan falls back to its fan mode preset without a wind setting."""
    entity_id = "fan.sl_fan"
    await set_node_attribute_and_notify(
        hass,
        matter_client,
        matter_node,
        endpoint=1,
        cluster_id=514,
        attribute_id=10,
        value=2,
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["preset_mode"] == "natural_wind"

    node_data = copy.deepcopy(matter_node.node_data)
    del node_data.attributes["1/514/10"]
    matter_node.update(node_data)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_UPDATED,
        matter_node,
        node_id=matter_node.node_id,
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["preset_mode"] == "low"


@pytest.mark.parametrize(
    ("node_fixture", "entity_id", "removed_path", "check_attribute"),
    [
        (
            "extended_color_light",
            "light.mock_extended_color_light",
            "1/8/0",
            "brightness",
        ),
        (
            "extended_color_light",
            "light.mock_extended_color_light",
            "1/768/0",
            "hs_color",
        ),
    ],
)
async def test_node_update_without_optional_attribute(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
    removed_path: str,
    check_attribute: str,
) -> None:
    """Test a node update without an optional attribute the entity reads.

    The client resets the endpoint to the node update, so the attribute reads as
    None even without a null value before it.
    """
    node_data = copy.deepcopy(matter_node.node_data)
    del node_data.attributes[removed_path]
    matter_node.update(node_data)
    await trigger_subscription_callback(
        hass,
        matter_client,
        EventType.NODE_UPDATED,
        matter_node,
        node_id=matter_node.node_id,
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"
    assert state.attributes[check_attribute] is None


async def test_bridged_node_without_device_info(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
) -> None:
    """Test a Bridged Node without BridgedDeviceBasicInformation is set up."""
    node = create_node_from_fixture("fritz_bridge")
    node_data = copy.deepcopy(node.node_data)
    node_data.attributes = {
        path: value
        for path, value in node_data.attributes.items()
        if not path.startswith("42/57/")
    }

    await _setup_integration_with_nodes(hass, matter_client, [MatterNode(node_data)])

    # the entities of endpoints 40 and 41 belong to the device of the Bridged Node (42)
    for endpoint_id in (40, 41):
        assert any(
            entity.platform == "matter" and f"-42-{endpoint_id}-" in entity.unique_id
            for entity in entity_registry.entities.values()
        )
