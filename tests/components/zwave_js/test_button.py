"""Test the Z-Wave JS button entities."""
from homeassistant.components.button.const import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.zwave_js.const import DOMAIN, SERVICE_REFRESH_VALUE
from homeassistant.components.zwave_js.helpers import get_valueless_base_unique_id
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.helpers.entity_registry import async_get


async def test_ping_entity(
    hass,
    client,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    controller_node,
    integration,
    caplog,
):
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

    assert "There is no value to refresh for this entity" in caplog.text

    # Assert a node ping button entity is not created for the controller
    driver = client.driver
    node = driver.controller.nodes[1]
    assert node.is_controller_node
    assert (
        async_get(hass).async_get_entity_id(
            DOMAIN, "sensor", f"{get_valueless_base_unique_id(driver, node)}.ping"
        )
        is None
    )
