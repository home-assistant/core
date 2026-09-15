"""Test KNX entity link."""

from typing import Any

from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import KNXTestKit

from tests.common import async_mock_service
from tests.typing import WebSocketGenerator

_STATUS_GA = "1/1/1"  # HA state -> KNX (outbound)
_COMMAND_GA = "2/2/2"  # KNX -> HA action (inbound)
_ENTITY_ID = "switch.test"


def _link_data(**overrides: Any) -> dict[str, Any]:
    """Build entity link data for a switch, with optional KNX option overrides."""
    return {
        "knx": {
            "ga_status": {"write": _STATUS_GA},
            "ga_command": {"state": _COMMAND_GA},
        }
        | overrides
    }


async def _create_switch_link(
    ws_client: Any, data: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Create a switch entity link via websocket and return the result."""
    await ws_client.send_json_auto_id(
        {
            "type": "knx/update_entity_link",
            "entity_id": _ENTITY_ID,
            "data": data if data is not None else _link_data(),
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
    await _create_switch_link(ws_client)

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
    await _create_switch_link(ws_client)
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
    await _create_switch_link(ws_client)
    async_mock_service(hass, "switch", SERVICE_TURN_ON)

    # the command itself does not echo (the service call hasn't changed state yet)
    await knx.receive_write(_COMMAND_GA, True)
    await hass.async_block_till_done()
    await knx.assert_no_telegram()

    # the entity reacts -> status feedback is sent on the status group address
    hass.states.async_set(_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()
    await knx.assert_write(_STATUS_GA, True)


async def test_switch_link_skips_unchanged_state(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test attribute-only updates do not repeat the status telegram."""
    await knx.setup_integration()
    ws_client = await hass_ws_client(hass)
    await _create_switch_link(ws_client)

    hass.states.async_set(_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()
    await knx.assert_write(_STATUS_GA, True)

    hass.states.async_set(_ENTITY_ID, STATE_ON, {"unrelated": 1})
    await hass.async_block_till_done()
    await knx.assert_no_telegram()


async def test_switch_link_responds_to_read(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a GroupValueRead on the status GA is answered."""
    await knx.setup_integration()
    ws_client = await hass_ws_client(hass)
    await _create_switch_link(ws_client)

    hass.states.async_set(_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()
    await knx.assert_write(_STATUS_GA, True)

    await knx.receive_read(_STATUS_GA)
    await knx.assert_response(_STATUS_GA, True)


async def test_switch_link_invert(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test invert applies to both directions."""
    await knx.setup_integration()
    ws_client = await hass_ws_client(hass)
    await _create_switch_link(ws_client, _link_data(invert=True))
    turn_off = async_mock_service(hass, "switch", SERVICE_TURN_OFF)

    hass.states.async_set(_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()
    await knx.assert_write(_STATUS_GA, False)

    await knx.receive_write(_COMMAND_GA, True)
    await hass.async_block_till_done()
    assert len(turn_off) == 1


async def test_switch_link_passive_command_address(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test passive command group addresses also drive the entity."""
    await knx.setup_integration()
    ws_client = await hass_ws_client(hass)
    await _create_switch_link(
        ws_client,
        {
            "knx": {
                "ga_status": {"write": _STATUS_GA},
                "ga_command": {"state": _COMMAND_GA, "passive": ["3/3/3"]},
            }
        },
    )
    turn_on = async_mock_service(hass, "switch", SERVICE_TURN_ON)

    await knx.receive_write("3/3/3", True)
    await hass.async_block_till_done()
    assert len(turn_on) == 1


async def test_switch_link_loaded_from_store(
    hass: HomeAssistant,
    knx: KNXTestKit,
) -> None:
    """Test links persisted in the config store are set up during integration setup."""
    hass.states.async_set(_ENTITY_ID, STATE_OFF)
    await knx.setup_integration(config_store_fixture="config_store_entity_link.json")
    turn_on = async_mock_service(hass, "switch", SERVICE_TURN_ON)

    # send_on_init: the state present at setup is sent to the status address
    await knx.assert_write(_STATUS_GA, False)

    await knx.receive_write(_COMMAND_GA, True)
    await hass.async_block_till_done()
    assert len(turn_on) == 1


async def test_switch_link_unload_removes_listeners(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test unloading the config entry detaches the link from state and bus."""
    await knx.setup_integration()
    ws_client = await hass_ws_client(hass)
    await _create_switch_link(ws_client)

    hass.states.async_set(_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()
    await knx.assert_write(_STATUS_GA, True)

    status_device = f"{_ENTITY_ID} ga_status"
    assert any(device.name == status_device for device in knx.xknx.devices)
    telegram_cb_count = len(knx.xknx.telegram_queue.telegram_received_cbs)

    await hass.config_entries.async_unload(knx.mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # the xknx device and the incoming telegram callback are gone
    assert not any(device.name == status_device for device in knx.xknx.devices)
    assert len(knx.xknx.telegram_queue.telegram_received_cbs) < telegram_cb_count

    # the state listener is gone: a state change no longer reaches the bus
    hass.states.async_set(_ENTITY_ID, STATE_OFF)
    await hass.async_block_till_done()
    await knx.assert_no_telegram()


async def test_switch_link_follows_entity_rename(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a link follows its entity when the entity_id is renamed."""
    entity_registry.async_get_or_create(
        "switch", "test", "unique", suggested_object_id="test"
    )
    await knx.setup_integration()
    ws_client = await hass_ws_client(hass)
    await _create_switch_link(ws_client)

    entity_registry.async_update_entity(_ENTITY_ID, new_entity_id="switch.renamed")
    await hass.async_block_till_done()

    # the stored config moved to the new key
    await ws_client.send_json_auto_id({"type": "knx/get_entity_links"})
    res = await ws_client.receive_json()
    assert res["success"], res
    assert set(res["result"]) == {"switch.renamed"}

    # outbound follows the new entity_id
    hass.states.async_set("switch.renamed", STATE_ON)
    await hass.async_block_till_done()
    await knx.assert_write(_STATUS_GA, True)

    # inbound now targets the new entity_id
    turn_off = async_mock_service(hass, "switch", SERVICE_TURN_OFF)
    await knx.receive_write(_COMMAND_GA, False)
    await hass.async_block_till_done()
    assert len(turn_off) == 1
    assert turn_off[0].data == {"entity_id": "switch.renamed"}

    # the old entity_id is detached
    hass.states.async_set(_ENTITY_ID, STATE_OFF)
    await hass.async_block_till_done()
    await knx.assert_no_telegram()


async def test_switch_link_rejects_self_loop(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a link with equal status and command group addresses is rejected."""
    await knx.setup_integration()
    ws_client = await hass_ws_client(hass)
    await ws_client.send_json_auto_id(
        {
            "type": "knx/validate_entity_link",
            "entity_id": _ENTITY_ID,
            "data": {
                "knx": {
                    "ga_status": {"write": _STATUS_GA},
                    "ga_command": {"state": _STATUS_GA},
                }
            },
        }
    )
    res = await ws_client.receive_json()
    assert res["success"], res
    assert res["result"]["success"] is False
    assert res["result"]["errors"]
