"""Test the Z-Wave JS button entities."""

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.zwave_js.const import DOMAIN, SERVICE_REFRESH_VALUE
from homeassistant.components.zwave_js.helpers import get_valueless_base_unique_id
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_ping_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    integration,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test ping entity."""
    client.async_send_command.return_value = {"responded": True}

    # Test successful ping call
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {
            ATTR_ENTITY_ID: "button.z_wave_thermostat_ping",
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.ping"
    assert (
        args["nodeId"]
        == climate_radio_thermostat_ct100_plus_different_endpoints.node_id
    )

    client.async_send_command.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_REFRESH_VALUE,
        {
            ATTR_ENTITY_ID: "button.z_wave_thermostat_ping",
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert "There is no value to refresh for this entity" in caplog.text

    # Assert a node ping button entity is not created for the controller
    driver = client.driver
    node = driver.controller.nodes[1]
    assert node.is_controller_node
    assert (
        entity_registry.async_get_entity_id(
            DOMAIN, "sensor", f"{get_valueless_base_unique_id(driver, node)}.ping"
        )
        is None
    )


async def test_notification_idle_button(
    hass: HomeAssistant, client, multisensor_6, integration
) -> None:
    """Test Notification idle button."""
    node = multisensor_6
    state = hass.states.get("button.multisensor_6_idle_home_security_cover_status")
    assert state
    assert state.state == "unknown"
    assert (
        state.attributes["friendly_name"]
        == "Multisensor 6 Idle Home Security Cover status"
    )

    # Test successful idle call
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {
            ATTR_ENTITY_ID: "button.multisensor_6_idle_home_security_cover_status",
        },
        blocking=True,
    )

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args_list[0][0][0]
    assert args["command"] == "node.manually_idle_notification_value"
    assert args["nodeId"] == node.node_id
    assert args["valueId"] == {
        "commandClass": 113,
        "endpoint": 0,
        "property": "Home Security",
        "propertyKey": "Cover status",
    }
