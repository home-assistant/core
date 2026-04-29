"""Test Matter entity behavior."""

from __future__ import annotations

from unittest.mock import MagicMock

from matter_server.client.models.node import MatterNode
from matter_server.common.models import EventType
import pytest

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    set_node_attribute,
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
    set_node_attribute(matter_node, 29, 57, 17, False)
    await trigger_subscription_callback(
        hass,
        matter_client,
        event=EventType.ATTRIBUTE_UPDATED,
        data=(matter_node.node_id, _REACHABLE_ATTR_PATH, False),
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
    set_node_attribute(matter_node, 29, 57, 17, True)
    await trigger_subscription_callback(
        hass,
        matter_client,
        event=EventType.ATTRIBUTE_UPDATED,
        data=(matter_node.node_id, _REACHABLE_ATTR_PATH, True),
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
        f"Expected a subscribe_events call with attr_path_filter={_REACHABLE_ATTR_PATH!r} "
        "and event_filter=ATTRIBUTE_UPDATED, but none was found."
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
        "Unexpected subscribe_events call for BridgedDeviceBasicInformation.Reachable on a non-bridged entity."
    )
