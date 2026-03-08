"""Test Matter binary sensors."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
from matter_server.common.models import EventType
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.matter.binary_sensor import (
    DISCOVERY_SCHEMAS as BINARY_SENSOR_SCHEMAS,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    set_node_attribute,
    snapshot_matter_entities,
    trigger_subscription_callback,
)


@pytest.fixture(autouse=True)
def binary_sensor_platform() -> Generator[None]:
    """Load only the binary sensor platform."""
    with patch(
        "homeassistant.components.matter.discovery.DISCOVERY_SCHEMAS",
        new={
            Platform.BINARY_SENSOR: BINARY_SENSOR_SCHEMAS,
        },
    ):
        yield


@pytest.mark.usefixtures("matter_devices")
async def test_binary_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test binary sensors."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.BINARY_SENSOR)


@pytest.mark.parametrize("node_fixture", ["mock_occupancy_sensor"])
async def test_occupancy_sensor(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test occupancy sensor."""
    state = hass.states.get("binary_sensor.mock_occupancy_sensor_occupancy")
    assert state
    assert state.state == "on"

    set_node_attribute(matter_node, 1, 1030, 0, 0)
    await trigger_subscription_callback(
        hass, matter_client, data=(matter_node.node_id, "1/1030/0", 0)
    )

    state = hass.states.get("binary_sensor.mock_occupancy_sensor_occupancy")
    assert state
    assert state.state == "off"


@pytest.mark.parametrize(
    ("node_fixture", "entity_id"),
    [
        ("eve_contact_sensor", "binary_sensor.eve_door_door"),
        ("mock_leak_sensor", "binary_sensor.water_leak_detector_water_leak"),
    ],
)
async def test_boolean_state_sensors(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    entity_id: str,
) -> None:
    """Test if binary sensors get created from devices with Boolean State cluster."""
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "on"

    # invert the value
    cur_attr_value = matter_node.get_attribute_value(1, 69, 0)
    set_node_attribute(matter_node, 1, 69, 0, not cur_attr_value)
    await trigger_subscription_callback(
        hass, matter_client, data=(matter_node.node_id, "1/69/0", not cur_attr_value)
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "off"


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
async def test_battery_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test battery sensor."""
    entity_id = "binary_sensor.mock_door_lock_battery"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "off"

    set_node_attribute(matter_node, 1, 47, 14, 1)
    await trigger_subscription_callback(
        hass, matter_client, data=(matter_node.node_id, "1/47/14", 1)
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "on"


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
async def test_actuator_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test actuator enabled sensor."""
    entity_id = "binary_sensor.mock_door_lock_actuator"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "on"

    set_node_attribute(matter_node, 1, 257, 2, False)
    await trigger_subscription_callback(
        hass, matter_client, data=(matter_node.node_id, "1/257/2", False)
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "off"


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
async def test_optional_sensor_from_featuremap(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test discovery of optional doorsensor in doorlock featuremap."""
    entity_id = "binary_sensor.mock_door_lock_door"
    state = hass.states.get(entity_id)
    assert state is None

    # update the feature map to include the optional door sensor feature
    # and fire a node updated event
    set_node_attribute(matter_node, 1, 257, 65532, 32)
    await trigger_subscription_callback(
        hass, matter_client, event=EventType.NODE_UPDATED, data=matter_node
    )
    # this should result in a new binary sensor entity being discovered
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "off"
    # now test the reverse, by removing the feature from the feature map
    set_node_attribute(matter_node, 1, 257, 65532, 0)
    await trigger_subscription_callback(
        hass, matter_client, data=(matter_node.node_id, "1/257/65532", 0)
    )
    state = hass.states.get(entity_id)
    assert state is None


@pytest.mark.parametrize("node_fixture", ["silabs_evse_charging"])
async def test_evse_sensor(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test evse sensors."""
    # Test StateEnum value with binary_sensor.evse_charging_status
    entity_id = "binary_sensor.evse_charging_status"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "on"
    # switch to PluggedInDemand state
    set_node_attribute(matter_node, 1, 153, 0, 2)
    await trigger_subscription_callback(
        hass, matter_client, data=(matter_node.node_id, "1/153/0", 2)
    )
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "off"

    # Test StateEnum value with binary_sensor.evse_plug
    entity_id = "binary_sensor.evse_plug"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "on"
    # switch to NotPluggedIn state
    set_node_attribute(matter_node, 1, 153, 0, 0)
    await trigger_subscription_callback(
        hass, matter_client, data=(matter_node.node_id, "1/153/0", 0)
    )
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "off"

    # Test SupplyStateEnum value with binary_sensor.evse_charger_supply_state
    entity_id = "binary_sensor.evse_charger_supply_state"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "on"
    # switch to Disabled state
    set_node_attribute(matter_node, 1, 153, 1, 0)
    await trigger_subscription_callback(
        hass, matter_client, data=(matter_node.node_id, "1/153/1", 0)
    )
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "off"


@pytest.mark.parametrize("node_fixture", ["silabs_water_heater"])
async def test_water_heater(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test water heater sensor."""
    # BoostState
    state = hass.states.get("binary_sensor.water_heater_boost_state")
    assert state
    assert state.state == "off"

    set_node_attribute(matter_node, 2, 148, 5, 1)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("binary_sensor.water_heater_boost_state")
    assert state
    assert state.state == "on"


@pytest.mark.parametrize("node_fixture", ["mock_pump"])
async def test_pump(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test pump sensors."""
    # PumpStatus
    state = hass.states.get("binary_sensor.mock_pump_running")
    assert state
    assert state.state == "on"

    set_node_attribute(matter_node, 1, 512, 16, 0)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("binary_sensor.mock_pump_running")
    assert state
    assert state.state == "off"

    # Initial state: kRunning bit only (no fault bits) should be off
    state = hass.states.get("binary_sensor.mock_pump_problem")
    assert state
    assert state.state == "off"

    # Set DeviceFault bit
    set_node_attribute(matter_node, 1, 512, 16, 1)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("binary_sensor.mock_pump_problem")
    assert state
    assert state.state == "on"

    # Clear all bits - problem sensor should be off
    set_node_attribute(matter_node, 1, 512, 16, 0)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("binary_sensor.mock_pump_problem")
    assert state
    assert state.state == "off"

    # Set SupplyFault bit
    set_node_attribute(matter_node, 1, 512, 16, 2)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("binary_sensor.mock_pump_problem")
    assert state
    assert state.state == "on"


@pytest.mark.parametrize("node_fixture", ["silabs_dishwasher"])
async def test_dishwasher_alarm(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test dishwasher alarm sensors."""
    state = hass.states.get("binary_sensor.dishwasher_door_alarm")
    assert state

    # set DoorAlarm alarm
    set_node_attribute(matter_node, 1, 93, 2, 4)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("binary_sensor.dishwasher_door_alarm")
    assert state
    assert state.state == "on"

    # clear DoorAlarm alarm
    set_node_attribute(matter_node, 1, 93, 2, 0)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("binary_sensor.dishwasher_inflow_alarm")
    assert state
    assert state.state == "off"

    # set InflowError alarm
    set_node_attribute(matter_node, 1, 93, 2, 1)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("binary_sensor.dishwasher_inflow_alarm")
    assert state
    assert state.state == "on"


@pytest.mark.parametrize("node_fixture", ["mock_valve"])
async def test_water_valve(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test valve alarms."""
    # ValveFault default state
    state = hass.states.get("binary_sensor.mock_valve_general_fault")
    assert state
    assert state.state == "off"

    state = hass.states.get("binary_sensor.mock_valve_valve_blocked")
    assert state
    assert state.state == "off"

    state = hass.states.get("binary_sensor.mock_valve_valve_leaking")
    assert state
    assert state.state == "off"

    # ValveFault general_fault test (bit 0)
    set_node_attribute(matter_node, 1, 129, 9, 1)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("binary_sensor.mock_valve_general_fault")
    assert state
    assert state.state == "on"

    state = hass.states.get("binary_sensor.mock_valve_valve_blocked")
    assert state
    assert state.state == "off"

    state = hass.states.get("binary_sensor.mock_valve_valve_leaking")
    assert state
    assert state.state == "off"

    # ValveFault valve_blocked test (bit 1)
    set_node_attribute(matter_node, 1, 129, 9, 2)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("binary_sensor.mock_valve_general_fault")
    assert state
    assert state.state == "off"

    state = hass.states.get("binary_sensor.mock_valve_valve_blocked")
    assert state
    assert state.state == "on"

    state = hass.states.get("binary_sensor.mock_valve_valve_leaking")
    assert state
    assert state.state == "off"

    # ValveFault valve_leaking test (bit 2)
    set_node_attribute(matter_node, 1, 129, 9, 4)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("binary_sensor.mock_valve_general_fault")
    assert state
    assert state.state == "off"

    state = hass.states.get("binary_sensor.mock_valve_valve_blocked")
    assert state
    assert state.state == "off"

    state = hass.states.get("binary_sensor.mock_valve_valve_leaking")
    assert state
    assert state.state == "on"

    # ValveFault multiple faults test (bits 0 and 2)
    set_node_attribute(matter_node, 1, 129, 9, 5)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("binary_sensor.mock_valve_general_fault")
    assert state
    assert state.state == "on"

    state = hass.states.get("binary_sensor.mock_valve_valve_blocked")
    assert state
    assert state.state == "off"

    state = hass.states.get("binary_sensor.mock_valve_valve_leaking")
    assert state
    assert state.state == "on"


@pytest.mark.parametrize("node_fixture", ["longan_link_thermostat"])
async def test_thermostat_occupancy(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test thermostat occupancy."""
    state = hass.states.get("binary_sensor.longan_link_hvac_occupancy")
    assert state
    assert state.state == "on"

    # Test Occupancy attribute change
    occupancy_attribute = clusters.Thermostat.Attributes.Occupancy

    set_node_attribute(
        matter_node,
        1,
        occupancy_attribute.cluster_id,
        occupancy_attribute.attribute_id,
        0,
    )
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("binary_sensor.longan_link_hvac_occupancy")
    assert state
    assert state.state == "off"


@pytest.mark.parametrize("node_fixture", ["eve_shutter"])
async def test_shutter_problem(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test shutter problem."""
    # Eve Shutter default state (ConfigStatus = 9)
    state = hass.states.get(
        "binary_sensor.eve_shutter_switch_20eci1701_configuration_status"
    )
    assert state
    assert state.state == "off"

    # Eve Shutter ConfigStatus Operational bit not set
    set_node_attribute(matter_node, 1, 258, 7, 8)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(
        "binary_sensor.eve_shutter_switch_20eci1701_configuration_status"
    )
    assert state
    assert state.state == "on"


@pytest.mark.parametrize("node_fixture", ["mock_thermostat"])
async def test_thermostat_remote_sensing(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test thermostat remote sensing binary sensors."""
    remote_sensing_attribute = clusters.Thermostat.Attributes.RemoteSensing

    # Test initial state (RemoteSensing = 0, all bits off)
    state = hass.states.get(
        "binary_sensor.mock_thermostat_local_temperature_remote_sensing"
    )
    assert state
    assert state.state == "off"

    state = hass.states.get(
        "binary_sensor.mock_thermostat_outdoor_temperature_remote_sensing"
    )
    assert state
    assert state.state == "off"

    state = hass.states.get("binary_sensor.mock_thermostat_occupancy_remote_sensing")
    assert state
    assert state.state == "off"

    # Set LocalTemperature bit (bit 0)
    set_node_attribute(
        matter_node,
        1,
        remote_sensing_attribute.cluster_id,
        remote_sensing_attribute.attribute_id,
        1,
    )
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(
        "binary_sensor.mock_thermostat_local_temperature_remote_sensing"
    )
    assert state
    assert state.state == "on"

    state = hass.states.get(
        "binary_sensor.mock_thermostat_outdoor_temperature_remote_sensing"
    )
    assert state
    assert state.state == "off"

    state = hass.states.get("binary_sensor.mock_thermostat_occupancy_remote_sensing")
    assert state
    assert state.state == "off"

    # Set OutdoorTemperature bit (bit 1)
    set_node_attribute(
        matter_node,
        1,
        remote_sensing_attribute.cluster_id,
        remote_sensing_attribute.attribute_id,
        2,
    )
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(
        "binary_sensor.mock_thermostat_local_temperature_remote_sensing"
    )
    assert state
    assert state.state == "off"

    state = hass.states.get(
        "binary_sensor.mock_thermostat_outdoor_temperature_remote_sensing"
    )
    assert state
    assert state.state == "on"

    state = hass.states.get("binary_sensor.mock_thermostat_occupancy_remote_sensing")
    assert state
    assert state.state == "off"

    # Set Occupancy bit (bit 2)
    set_node_attribute(
        matter_node,
        1,
        remote_sensing_attribute.cluster_id,
        remote_sensing_attribute.attribute_id,
        4,
    )
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(
        "binary_sensor.mock_thermostat_local_temperature_remote_sensing"
    )
    assert state
    assert state.state == "off"

    state = hass.states.get(
        "binary_sensor.mock_thermostat_outdoor_temperature_remote_sensing"
    )
    assert state
    assert state.state == "off"

    state = hass.states.get("binary_sensor.mock_thermostat_occupancy_remote_sensing")
    assert state
    assert state.state == "on"

    # Set multiple bits (bits 0 and 2 = value 5)
    set_node_attribute(
        matter_node,
        1,
        remote_sensing_attribute.cluster_id,
        remote_sensing_attribute.attribute_id,
        5,
    )
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(
        "binary_sensor.mock_thermostat_local_temperature_remote_sensing"
    )
    assert state
    assert state.state == "on"

    state = hass.states.get(
        "binary_sensor.mock_thermostat_outdoor_temperature_remote_sensing"
    )
    assert state
    assert state.state == "off"

    state = hass.states.get("binary_sensor.mock_thermostat_occupancy_remote_sensing")
    assert state
    assert state.state == "on"

    # Set all bits (value 7)
    set_node_attribute(
        matter_node,
        1,
        remote_sensing_attribute.cluster_id,
        remote_sensing_attribute.attribute_id,
        7,
    )
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(
        "binary_sensor.mock_thermostat_local_temperature_remote_sensing"
    )
    assert state
    assert state.state == "on"

    state = hass.states.get(
        "binary_sensor.mock_thermostat_outdoor_temperature_remote_sensing"
    )
    assert state
    assert state.state == "on"

    state = hass.states.get("binary_sensor.mock_thermostat_occupancy_remote_sensing")
    assert state
    assert state.state == "on"


@pytest.mark.parametrize("node_fixture", ["heiman_smoke_detector"])
async def test_smoke_detector(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test smoke detector sensor."""
    smoke_state_attribute = clusters.SmokeCoAlarm.Attributes.SmokeState

    # Test initial state (SmokeState = 0, kNormal)
    state = hass.states.get("binary_sensor.smoke_sensor_smoke")
    assert state
    assert state.state == "off"

    # Set SmokeState to kWarning (value 1)
    set_node_attribute(
        matter_node,
        1,
        smoke_state_attribute.cluster_id,
        smoke_state_attribute.attribute_id,
        1,
    )
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("binary_sensor.smoke_sensor_smoke")
    assert state
    assert state.state == "on"

    # Set SmokeState to kCritical (value 2)
    set_node_attribute(
        matter_node,
        1,
        smoke_state_attribute.cluster_id,
        smoke_state_attribute.attribute_id,
        2,
    )
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("binary_sensor.smoke_sensor_smoke")
    assert state
    assert state.state == "on"

    # Set SmokeState back to kNormal (value 0)
    set_node_attribute(
        matter_node,
        1,
        smoke_state_attribute.cluster_id,
        smoke_state_attribute.attribute_id,
        0,
    )
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("binary_sensor.smoke_sensor_smoke")
    assert state
    assert state.state == "off"


@pytest.mark.parametrize("node_fixture", ["heiman_co_sensor"])
async def test_co_detector(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test CO detector sensor."""
    co_state_attribute = clusters.SmokeCoAlarm.Attributes.COState

    # Test initial state (COState = 0, kNormal)
    state = hass.states.get("binary_sensor.smart_co_sensor_carbon_monoxide")
    assert state
    assert state.state == "off"

    # Set COState to kWarning (value 1)
    set_node_attribute(
        matter_node,
        1,
        co_state_attribute.cluster_id,
        co_state_attribute.attribute_id,
        1,
    )
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("binary_sensor.smart_co_sensor_carbon_monoxide")
    assert state
    assert state.state == "on"

    # Set COState to kCritical (value 2)
    set_node_attribute(
        matter_node,
        1,
        co_state_attribute.cluster_id,
        co_state_attribute.attribute_id,
        2,
    )
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("binary_sensor.smart_co_sensor_carbon_monoxide")
    assert state
    assert state.state == "on"

    # Set COState back to kNormal (value 0)
    set_node_attribute(
        matter_node,
        1,
        co_state_attribute.cluster_id,
        co_state_attribute.attribute_id,
        0,
    )
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("binary_sensor.smart_co_sensor_carbon_monoxide")
    assert state
    assert state.state == "off"
