"""KNX Websocket Tests."""
from homeassistant.components.knx import KNX_ADDRESS, SwitchSchema
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from .conftest import KNXTestKit


async def test_knx_info_command(hass: HomeAssistant, knx: KNXTestKit, hass_ws_client):
    """Test knx/info command."""
    await knx.setup_integration({})

    client = await hass_ws_client(hass)

    await client.send_json({"id": 6, "type": "knx/info"})

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["version"] is not None
    assert res["result"]["connected"]
    assert res["result"]["current_address"] == "0.0.0"


async def test_knx_subscribe_telegrams_command(
    hass: HomeAssistant, knx: KNXTestKit, hass_ws_client
):
    """Test knx/subscribe_telegrams command."""
    await knx.setup_integration(
        {
            SwitchSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: "1/2/4",
            }
        }
    )
    assert len(hass.states.async_all()) == 1

    client = await hass_ws_client(hass)

    await client.send_json({"id": 6, "type": "knx/subscribe_telegrams"})

    res = await client.receive_json()
    assert res["success"], res

    # send incoming events
    await knx.receive_read("1/2/3")
    await knx.receive_write("1/3/4", True)
    await knx.receive_write("1/3/4", False)
    await knx.receive_write("1/3/8", (0x34, 0x45))
    # send outgoing events
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.test"}, blocking=True
    )
    await knx.assert_write("1/2/4", True)

    # receive events
    res = await client.receive_json()
    assert res["event"]["destination_address"] == "1/2/3"
    assert res["event"]["payload"] == ""
    assert res["event"]["type"] == "GroupValueRead"
    assert res["event"]["source_address"] == "1.2.3"
    assert res["event"]["direction"] == "label.incoming"
    assert res["event"]["timestamp"] is not None

    res = await client.receive_json()
    assert res["event"]["destination_address"] == "1/3/4"
    assert res["event"]["payload"] == '<DPTBinary value="True" />'
    assert res["event"]["type"] == "GroupValueWrite"
    assert res["event"]["source_address"] == "1.2.3"
    assert res["event"]["direction"] == "label.incoming"
    assert res["event"]["timestamp"] is not None

    res = await client.receive_json()
    assert res["event"]["destination_address"] == "1/3/4"
    assert res["event"]["payload"] == '<DPTBinary value="False" />'
    assert res["event"]["type"] == "GroupValueWrite"
    assert res["event"]["source_address"] == "1.2.3"
    assert res["event"]["direction"] == "label.incoming"
    assert res["event"]["timestamp"] is not None

    res = await client.receive_json()
    assert res["event"]["destination_address"] == "1/3/8"
    assert res["event"]["payload"] == '<DPTArray value="[0x34,0x45]" />'
    assert res["event"]["type"] == "GroupValueWrite"
    assert res["event"]["source_address"] == "1.2.3"
    assert res["event"]["direction"] == "label.incoming"
    assert res["event"]["timestamp"] is not None

    res = await client.receive_json()
    assert res["event"]["destination_address"] == "1/2/4"
    assert res["event"]["payload"] == '<DPTBinary value="True" />'
    assert res["event"]["type"] == "GroupValueWrite"
    assert (
        res["event"]["source_address"] == "0.0.0"
    )  # needs to be the currently connected IA connected to
    assert res["event"]["direction"] == "label.outgoing"
    assert res["event"]["timestamp"] is not None
