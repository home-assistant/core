"""Test Matter sensors."""

from unittest.mock import MagicMock, call

from matter_server.client.models.node import MatterNode
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_HIGH_DEMAND,
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
    """Test water heater sensor."""
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

    # test BoostState update from device
    set_node_attribute(matter_node, 2, 148, 5, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("water_heater.water_heater")
    assert state.state == STATE_HIGH_DEMAND


@pytest.mark.parametrize("node_fixture", ["silabs_water_heater"])
async def test_water_heater_service_calls(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test water_heater platform service calls."""
    # test single-setpoint temperature adjustment when boost mode is active
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
