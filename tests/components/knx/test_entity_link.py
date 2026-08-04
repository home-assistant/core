"""Test KNX entity link."""

from typing import Any

from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .conftest import KNXTestKit

from tests.common import async_mock_service
from tests.typing import WebSocketGenerator

_STATUS_GA = "1/1/1"  # HA state -> KNX (outbound)
_COMMAND_GA = "2/2/2"  # KNX -> HA action (inbound)
_ENTITY_ID = "switch.test"


async def _create_switch_link(
    ws_client: Any, channels: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Create a switch entity link via websocket and return the result."""
    await ws_client.send_json_auto_id(
        {
            "type": "knx/create_entity_link",
            "platform": "switch",
            "entity_id": _ENTITY_ID,
            "channels": channels,
        }
    )
    res = await ws_client.receive_json()
    assert res["success"], res
    return res["result"]


async def test_switch_link_outbound(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a Home Assistant state change is sent to the status group address."""
    await knx.setup_integration()
    ws_client = await hass_ws_client(hass)
    result = await _create_switch_link(
        ws_client, {"switch": {"write": _STATUS_GA, "state": _COMMAND_GA}}
    )
    assert result["entity_id"] == _ENTITY_ID

    hass.states.async_set(_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()
    await knx.assert_write(_STATUS_GA, True)

    hass.states.async_set(_ENTITY_ID, STATE_OFF)
    await hass.async_block_till_done()
    await knx.assert_write(_STATUS_GA, False)


async def test_switch_link_inbound(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test an incoming command telegram drives the entity via a service call."""
    await knx.setup_integration()
    ws_client = await hass_ws_client(hass)
    await _create_switch_link(
        ws_client, {"switch": {"write": _STATUS_GA, "state": _COMMAND_GA}}
    )
    turn_on = async_mock_service(hass, "switch", SERVICE_TURN_ON)
    turn_off = async_mock_service(hass, "switch", SERVICE_TURN_OFF)

    await knx.receive_write(_COMMAND_GA, True)
    await hass.async_block_till_done()
    assert len(turn_on) == 1
    assert turn_on[0].data == {"entity_id": _ENTITY_ID}

    await knx.receive_write(_COMMAND_GA, False)
    await hass.async_block_till_done()
    assert len(turn_off) == 1


async def test_switch_link_status_feedback(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a bus-driven change is fed back on the (distinct) status GA, not looped."""
    await knx.setup_integration()
    ws_client = await hass_ws_client(hass)
    await _create_switch_link(
        ws_client, {"switch": {"write": _STATUS_GA, "state": _COMMAND_GA}}
    )
    async_mock_service(hass, "switch", SERVICE_TURN_ON)

    # the command itself does not echo (the service call hasn't changed state yet)
    await knx.receive_write(_COMMAND_GA, True)
    await hass.async_block_till_done()
    await knx.assert_no_telegram()

    # the entity reacts -> status feedback is sent on the status group address
    hass.states.async_set(_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()
    await knx.assert_write(_STATUS_GA, True)


async def test_switch_link_rejects_self_loop(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a channel with equal status and command group addresses is rejected."""
    await knx.setup_integration()
    ws_client = await hass_ws_client(hass)
    await ws_client.send_json_auto_id(
        {
            "type": "knx/validate_entity_link",
            "platform": "switch",
            "entity_id": _ENTITY_ID,
            "channels": {"switch": {"write": _STATUS_GA, "state": _STATUS_GA}},
        }
    )
    res = await ws_client.receive_json()
    assert res["success"], res
    assert res["result"]["success"] is False
    assert res["result"]["errors"][0]["path"] == ["channels", "switch"]
