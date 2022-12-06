"""Test Matter binary sensors."""
from unittest.mock import MagicMock

from matter_server.common.models.node import MatterNode
import pytest

from homeassistant.core import HomeAssistant

from .common import (
    set_node_attribute,
    setup_integration_with_node_fixture,
    trigger_subscription_callback,
)


@pytest.fixture(name="contact_sensor_node")
async def contact_sensor_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a contact sensor node."""
    return await setup_integration_with_node_fixture(
        hass, "contact-sensor", matter_client
    )


async def test_contact_sensor(
    hass: HomeAssistant,
    matter_client: MagicMock,
    contact_sensor_node: MatterNode,
) -> None:
    """Test contact sensor."""
    state = hass.states.get("binary_sensor.mock_contact_sensor_contact")
    assert state
    assert state.state == "on"

    set_node_attribute(contact_sensor_node, 1, 69, 0, False)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("binary_sensor.mock_contact_sensor_contact")
    assert state
    assert state.state == "off"
