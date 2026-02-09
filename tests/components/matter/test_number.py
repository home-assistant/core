"""Test Matter number entities."""

from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
from matter_server.common import custom_clusters
from matter_server.common.errors import MatterError
from matter_server.common.helpers.util import create_attribute_path_from_attribute
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.matter.models import (
    MatterDiscoverySchema,
    MatterEntityInfo,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common import (
    set_node_attribute,
    snapshot_matter_entities,
    trigger_subscription_callback,
)


@pytest.mark.usefixtures("matter_devices")
async def test_numbers(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test numbers."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.NUMBER)


@pytest.mark.parametrize("node_fixture", ["mock_dimmable_light"])
async def test_level_control_config_entities(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test number entities are created for the LevelControl cluster (config) attributes."""
    state = hass.states.get("number.mock_dimmable_light_on_level")
    assert state
    assert state.state == "255"

    state = hass.states.get("number.mock_dimmable_light_on_transition_time")
    assert state
    assert state.state == "0.0"

    state = hass.states.get("number.mock_dimmable_light_off_transition_time")
    assert state
    assert state.state == "0.0"

    state = hass.states.get("number.mock_dimmable_light_on_off_transition_time")
    assert state
    assert state.state == "0.0"

    set_node_attribute(matter_node, 1, 0x00000008, 0x0011, 20)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("number.mock_dimmable_light_on_level")
    assert state
    assert state.state == "20"


@pytest.mark.parametrize("node_fixture", ["eve_weather_sensor"])
async def test_eve_weather_sensor_altitude(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test weather sensor created from (Eve) custom cluster."""
    # pressure sensor on Eve custom cluster
    state = hass.states.get("number.eve_weather_altitude_above_sea_level")
    assert state
    assert state.state == "40.0"

    set_node_attribute(matter_node, 1, 319486977, 319422483, 800)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("number.eve_weather_altitude_above_sea_level")
    assert state
    assert state.state == "800.0"

    # test set value
    await hass.services.async_call(
        "number",
        "set_value",
        {
            "entity_id": "number.eve_weather_altitude_above_sea_level",
            "value": 500,
        },
        blocking=True,
    )
    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args_list[0] == call(
        node_id=matter_node.node_id,
        attribute_path=create_attribute_path_from_attribute(
            endpoint_id=1,
            attribute=custom_clusters.EveCluster.Attributes.Altitude,
        ),
        value=500,
    )


@pytest.mark.parametrize("node_fixture", ["silabs_refrigerator"])
async def test_temperature_control_temperature_setpoint(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test TemperatureSetpoint from TemperatureControl."""
    # TemperatureSetpoint
    state = hass.states.get("number.refrigerator_temperature_setpoint_2")
    assert state
    assert state.state == "-18.0"

    set_node_attribute(matter_node, 2, 86, 0, -1600)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("number.refrigerator_temperature_setpoint_2")
    assert state
    assert state.state == "-16.0"

    # test set value
    await hass.services.async_call(
        "number",
        "set_value",
        {
            "entity_id": "number.refrigerator_temperature_setpoint_2",
            "value": -17,
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=2,
        command=clusters.TemperatureControl.Commands.SetTemperature(
            targetTemperature=-1700
        ),
    )


@pytest.mark.parametrize("node_fixture", ["mock_dimmable_light"])
async def test_matter_exception_on_write_attribute(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test if a MatterError gets converted to HomeAssistantError by using a dimmable_light fixture."""
    state = hass.states.get("number.mock_dimmable_light_on_level")
    assert state
    matter_client.write_attribute.side_effect = MatterError("Boom")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "number",
            "set_value",
            {
                "entity_id": "number.mock_dimmable_light_on_level",
                "value": 500,
            },
            blocking=True,
        )


@pytest.mark.parametrize("node_fixture", ["mock_pump"])
async def test_pump_level(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test level control for pump."""
    # CurrentLevel on LevelControl cluster
    state = hass.states.get("number.mock_pump_setpoint")
    assert state
    assert state.state == "100.0"

    set_node_attribute(matter_node, 1, 8, 0, 100)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("number.mock_pump_setpoint")
    assert state
    assert state.state == "50.0"

    # test set value
    await hass.services.async_call(
        "number",
        "set_value",
        {
            "entity_id": "number.mock_pump_setpoint",
            "value": 75,
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert (
        matter_client.send_device_command.call_args
        == call(
            node_id=matter_node.node_id,
            endpoint_id=1,
            command=clusters.LevelControl.Commands.MoveToLevel(
                level=150
            ),  # 75 * 2 = 150, as the value is multiplied by 2 in the HA to native value conversion
        )
    )


@pytest.mark.parametrize("node_fixture", ["mock_microwave_oven"])
async def test_microwave_oven(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test Cooktime for microwave oven."""

    # Cooktime on MicrowaveOvenControl cluster (1/96/2)
    state = hass.states.get("number.mock_microwave_oven_cooking_time")
    assert state
    assert state.state == "30"

    # test set value
    await hass.services.async_call(
        "number",
        "set_value",
        {
            "entity_id": "number.mock_microwave_oven_cooking_time",
            "value": 60,  # 60 seconds
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.MicrowaveOvenControl.Commands.SetCookingParameters(
            cookTime=60,  # 60 seconds
        ),
    )


@pytest.mark.parametrize("node_fixture", ["aqara_thermostat_w500"])
async def test_thermostat_occupied_setback(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test thermostat occupied setback number entity."""

    entity_id = "number.floor_heating_thermostat_occupied_setback"

    # Initial value comes from 1/513/52 with scale /10 (5 -> 0.5 °C)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "0.5"

    # Update attribute to 30 (-> 3.0 °C)
    set_node_attribute(matter_node, 1, 513, 52, 30)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "3.0"

    # Setting value to 2.0 °C writes 20 to OccupiedSetback (scale x10)
    await hass.services.async_call(
        "number",
        "set_value",
        {
            "entity_id": entity_id,
            "value": 2.0,
        },
        blocking=True,
    )

    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path=create_attribute_path_from_attribute(
            endpoint_id=1,
            attribute=clusters.Thermostat.Attributes.OccupiedSetback,
        ),
        value=20,
    )


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
async def test_lock_attributes(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test door lock attributes."""
    # WrongCodeEntryLimit for door lock
    state = hass.states.get("number.mock_door_lock_wrong_code_limit")
    assert state
    assert state.state == "3"

    set_node_attribute(matter_node, 1, 257, 48, 10)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("number.mock_door_lock_wrong_code_limit")
    assert state
    assert state.state == "10"

    # UserCodeTemporaryDisableTime for door lock
    state = hass.states.get("number.mock_door_lock_user_code_temporary_disable_time")
    assert state
    assert state.state == "10"

    set_node_attribute(matter_node, 1, 257, 49, 30)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("number.mock_door_lock_user_code_temporary_disable_time")
    assert state
    assert state.state == "30"


@pytest.mark.parametrize("node_fixture", ["mock_door_lock"])
async def test_matter_exception_on_door_lock_write_attribute(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test that MatterError is handled for write_attribute call."""
    entity_id = "number.mock_door_lock_wrong_code_limit"
    state = hass.states.get(entity_id)
    assert state
    matter_client.write_attribute.side_effect = MatterError("Boom!")
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            "number",
            "set_value",
            {
                "entity_id": entity_id,
                "value": 1,
            },
            blocking=True,
        )

    assert str(exc_info.value) == "Boom!"


class MockEndpoint:
    """Mock Matter endpoint for testing cluster revision filtering."""

    def __init__(self, cluster_revision: int | None = None) -> None:
        """Initialize mock endpoint."""
        self.endpoint_id = 1
        self.cluster_revision = cluster_revision

    def has_attribute(self, cluster: int, attribute: int) -> bool:
        """Check if endpoint has attribute."""
        return True

    def get_attribute_value(self, cluster_id: int, attribute_id: int) -> int | None:
        """Get attribute value."""
        # Return cluster revision for attribute 0xFFFD (65533)
        if attribute_id == 65533:
            return self.cluster_revision
        return None


@pytest.mark.parametrize(
    (
        "cluster_revision",
        "cluster_revision_min",
        "cluster_revision_max",
        "should_match",
    ),
    [
        # No constraints - should match any revision
        (5, None, None, True),
        (6, None, None, True),
        (7, None, None, True),
        # Min constraint only
        (5, 6, None, False),  # 5 < 6
        (6, 6, None, True),  # 6 >= 6
        (7, 6, None, True),  # 7 >= 6
        # Max constraint only
        (5, None, 6, True),  # 5 <= 6
        (6, None, 6, True),  # 6 <= 6
        (7, None, 6, False),  # 7 > 6
        # Both min and max constraints
        (4, 5, 7, False),  # 4 < 5
        (5, 5, 7, True),  # 5 >= 5 and <= 7
        (6, 5, 7, True),  # 6 >= 5 and <= 7
        (7, 5, 7, True),  # 7 >= 5 and <= 7
        (8, 5, 7, False),  # 8 > 7
    ],
)
def test_cluster_revision_filtering(
    cluster_revision: int | None,
    cluster_revision_min: int | None,
    cluster_revision_max: int | None,
    should_match: bool,
) -> None:
    """Test cluster revision filtering logic."""
    # Create discovery schema with cluster revision constraints
    schema = MatterDiscoverySchema(
        platform=Platform.NUMBER,
        entity_description=MagicMock(),
        entity_class=MagicMock(),
        required_attributes=(
            clusters.Thermostat.Attributes.LocalTemperatureCalibration,
        ),
        cluster_revision_min=cluster_revision_min,
        cluster_revision_max=cluster_revision_max,
    )

    # Simulate the filtering logic from async_discover_entities
    # Check if entity should match based on cluster revision constraints
    if cluster_revision is not None and (
        (
            schema.cluster_revision_min is not None
            and cluster_revision < schema.cluster_revision_min
        )
        or (
            schema.cluster_revision_max is not None
            and cluster_revision > schema.cluster_revision_max
        )
    ):
        result = False
    else:
        result = True

    assert result == should_match, (
        f"Cluster revision {cluster_revision} with min={cluster_revision_min}, "
        f"max={cluster_revision_max} should {'match' if should_match else 'not match'}"
    )


def test_cluster_revision_stored_in_entity_info() -> None:
    """Test that cluster revision value is stored in MatterEntityInfo."""
    # Create entity info with cluster revision
    entity_info = MatterEntityInfo(
        endpoint=MockEndpoint(cluster_revision=7),
        platform=Platform.NUMBER,
        attributes_to_watch=[
            clusters.Thermostat.Attributes.LocalTemperatureCalibration
        ],
        entity_description=MagicMock(),
        entity_class=MagicMock(),
        discovery_schema=MagicMock(),
        cluster_revision=7,
    )

    # Verify cluster revision is stored
    assert entity_info.cluster_revision == 7


def test_cluster_revision_none_when_not_required() -> None:
    """Test that cluster revision is None when not required by schema."""
    # Create entity info without cluster revision constraints
    entity_info = MatterEntityInfo(
        endpoint=MockEndpoint(),
        platform=Platform.NUMBER,
        attributes_to_watch=[
            clusters.Thermostat.Attributes.LocalTemperatureCalibration
        ],
        entity_description=MagicMock(),
        entity_class=MagicMock(),
        discovery_schema=MagicMock(),
        cluster_revision=None,
    )

    # Verify cluster revision is None
    assert entity_info.cluster_revision is None
