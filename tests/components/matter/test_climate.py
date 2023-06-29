"""Test Matter locks."""
from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
import pytest

from homeassistant.components.climate import (
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
)
from homeassistant.core import HomeAssistant

from .common import (
    set_node_attribute,
    setup_integration_with_node_fixture,
    trigger_subscription_callback,
)


@pytest.fixture(name="thermostat")
async def thermostat_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a thermostat node."""
    return await setup_integration_with_node_fixture(hass, "thermostat", matter_client)


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_thermostat(
    hass: HomeAssistant,
    matter_client: MagicMock,
    thermostat: MatterNode,
) -> None:
    """Test thermostat."""
    # change system mode to heat
    set_node_attribute(thermostat, 1, 513, 28, 4)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.state == HVAC_MODE_HEAT

    # change occupied heating setpoint to 20
    set_node_attribute(thermostat, 1, 513, 18, 2000)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["temperature"] == 20

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.longan_link_hvac",
            "temperature": 25,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=thermostat.node_id,
        endpoint_id=1,
        command=clusters.Thermostat.Commands.SetpointRaiseLower(
            clusters.Thermostat.Enums.SetpointAdjustMode.kHeat,
            50,
        ),
    )
    matter_client.send_device_command.reset_mock()

    # change system mode to cool
    set_node_attribute(thermostat, 1, 513, 28, 3)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.state == HVAC_MODE_COOL

    # change occupied cooling setpoint to 18
    set_node_attribute(thermostat, 1, 513, 17, 1800)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["temperature"] == 18

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.longan_link_hvac",
            "temperature": 16,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=thermostat.node_id,
        endpoint_id=1,
        command=clusters.Thermostat.Commands.SetpointRaiseLower(
            clusters.Thermostat.Enums.SetpointAdjustMode.kCool, -20
        ),
    )
    matter_client.send_device_command.reset_mock()
