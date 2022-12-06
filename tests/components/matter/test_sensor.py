"""Test Matter sensors."""
from unittest.mock import MagicMock

from matter_server.common.models.node import MatterNode
import pytest

from homeassistant.core import HomeAssistant

from .common import (
    set_node_attribute,
    setup_integration_with_node_fixture,
    trigger_subscription_callback,
)


@pytest.fixture(name="temperature_sensor_node")
async def temperature_sensor_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a temperature sensor node."""
    return await setup_integration_with_node_fixture(
        hass, "temperature-sensor", matter_client
    )


async def test_temperature_sensor(
    hass: HomeAssistant,
    matter_client: MagicMock,
    temperature_sensor_node: MatterNode,
) -> None:
    """Test temperature sensor."""
    state = hass.states.get("sensor.mock_temperature_sensor_temperature")
    assert state
    assert state.state == "21.0"

    set_node_attribute(temperature_sensor_node, 1, 1026, 0, 2500)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.mock_temperature_sensor_temperature")
    assert state
    assert state.state == "25.0"
