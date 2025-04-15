"""Test Matter sensors."""

from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
from matter_server.common.helpers.util import create_attribute_path_from_attribute
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_HIGH_DEMAND,
    STATE_OFF,
    WaterHeaterEntityFeature,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    set_node_attribute,
    snapshot_matter_entities,
    trigger_subscription_callback,
)


@pytest.mark.usefixtures("matter_devices")
async def test_water_heaters(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test water heaters."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.WATER_HEATER)


@pytest.mark.parametrize("node_fixture", ["silabs_water_heater"])
async def test_water_heater(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test water heater entity."""
    state = hass.states.get("water_heater.water_heater")
    assert state
    assert state.attributes["min_temp"] == 40
    assert state.attributes["max_temp"] == 65
    assert state.attributes["temperature"] == 65
    assert state.attributes["operation_list"] == ["eco", "high_demand", "off"]
    assert state.state == STATE_ECO

    # test supported features correctly parsed
    mask = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.ON_OFF
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    assert state.attributes["supported_features"] & mask == mask


@pytest.mark.parametrize("node_fixture", ["silabs_water_heater"])
async def test_water_heater_set_temperature(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test water_heater set temperature service."""
    # test single-setpoint temperature adjustment when eco mode is active
    state = hass.states.get("water_heater.water_heater")

    assert state
    assert state.state == STATE_ECO
    await hass.services.async_call(
        "water_heater",
        "set_temperature",
        {
            "entity_id": "water_heater.water_heater",
            "temperature": 52,
        },
        blocking=True,
    )

    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path="2/513/18",
        value=5200,
    )
    matter_client.write_attribute.reset_mock()

    @pytest.mark.parametrize("node_fixture", ["silabs_water_heater"])
    @pytest.mark.parametrize(
        ("operation_mode", "matter_attribute_value"),
        [(STATE_OFF, 0), (STATE_ECO, 4), (STATE_HIGH_DEMAND, 4)],
    )
    async def test_water_heater_set_operation_mode(
        hass: HomeAssistant,
        matter_client: MagicMock,
        matter_node: MatterNode,
        operation_mode: str,
        matter_attribute_value: int,
    ) -> None:
        """Test water_heater set operation mode service."""
        state = hass.states.get("water_heater.water_heater")
        assert state

        # test change mode to each operation_mode
        await hass.services.async_call(
            "water_heater",
            "set_operation_mode",
            {
                "entity_id": "water_heater.water_heater",
                "operation_mode": operation_mode,
            },
            blocking=True,
        )

        state = hass.states.get("water_heater.water_heater")
        assert state.state == operation_mode
        assert matter_client.write_attribute.call_count == 1
        assert matter_client.write_attribute.call_args == call(
            node_id=matter_node.node_id,
            attribute_path=create_attribute_path_from_attribute(
                endpoint_id=2,
                attribute=clusters.Thermostat.Attributes.SystemMode,
            ),
            value=matter_attribute_value,
        )

    @pytest.mark.parametrize("node_fixture", ["silabs_water_heater"])
    async def test_update_from_water_heater(
        hass: HomeAssistant,
        matter_client: MagicMock,
        matter_node: MatterNode,
    ) -> None:
        """Test enable boost from water heater device side."""
        state = hass.states.get("water_heater.water_heater")
        assert state

        set_node_attribute(matter_node, 2, 148, 5, 1)
        await trigger_subscription_callback(hass, matter_client)
        state = hass.states.get("water_heater.water_heater")
        assert state.state == STATE_HIGH_DEMAND
