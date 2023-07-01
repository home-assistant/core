"""Test Matter locks."""
from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
import pytest

from homeassistant.components.climate import (
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
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
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["min_temp"] == 16
    assert state.attributes["max_temp"] == 30
    assert state.attributes["hvac_modes"] == [
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT,
        HVAC_MODE_OFF,
        HVAC_MODE_HEAT_COOL,
    ]
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

    # change system mode to heat_cool
    set_node_attribute(thermostat, 1, 513, 28, 1)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.state == HVAC_MODE_HEAT_COOL

    # change occupied cooling setpoint to 18
    set_node_attribute(thermostat, 1, 513, 17, 2500)
    await trigger_subscription_callback(hass, matter_client)
    # change occupied heating setpoint to 18
    set_node_attribute(thermostat, 1, 513, 18, 1700)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["target_temp_low"] == 17
    assert state.attributes["target_temp_high"] == 25

    # change target_temp_low to 18
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.longan_link_hvac",
            "target_temp_low": 18,
            "target_temp_high": 25,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=thermostat.node_id,
        endpoint_id=1,
        command=clusters.Thermostat.Commands.SetpointRaiseLower(
            clusters.Thermostat.Enums.SetpointAdjustMode.kHeat, 10
        ),
    )
    matter_client.send_device_command.reset_mock()
    set_node_attribute(thermostat, 1, 513, 18, 1800)
    await trigger_subscription_callback(hass, matter_client)

    # change target_temp_high to 26
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.longan_link_hvac",
            "target_temp_low": 18,
            "target_temp_high": 26,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=thermostat.node_id,
        endpoint_id=1,
        command=clusters.Thermostat.Commands.SetpointRaiseLower(
            clusters.Thermostat.Enums.SetpointAdjustMode.kCool, 10
        ),
    )
    matter_client.send_device_command.reset_mock()
    set_node_attribute(thermostat, 1, 513, 17, 2600)
    await trigger_subscription_callback(hass, matter_client)
