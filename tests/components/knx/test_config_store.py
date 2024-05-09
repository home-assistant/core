"""Test KNX devices."""

from typing import Any

from homeassistant.components.knx.storage.config_store import (
    STORAGE_KEY as KNX_CONFIG_STORAGE_KEY,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import KNXTestKit

from tests.typing import WebSocketGenerator


async def test_create_switch(
    hass: HomeAssistant,
    knx: KNXTestKit,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test entity creation."""
    await knx.setup_integration({})
    client = await hass_ws_client(hass)

    test_name = "Test no device"
    test_entity_id = "switch.test_no_device"
    assert not entity_registry.async_get(test_entity_id)

    await client.send_json_auto_id(
        {
            "type": "knx/create_entity",
            "platform": Platform.SWITCH,
            "data": {
                "entity": {"name": test_name},
                "knx": {"ga_switch": {"write": "1/2/3"}},
            },
        }
    )
    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["success"] is True
    assert res["result"]["entity_id"] == test_entity_id

    entity = entity_registry.async_get(test_entity_id)
    assert entity

    # Test if entity is correctly stored in registry
    await client.send_json_auto_id({"type": "knx/get_entity_entries"})
    res = await client.receive_json()
    assert res["success"], res
    assert res["result"] == [
        entity.extended_dict,
    ]
    # Test if entity is correctly stored in config store
    await client.send_json_auto_id(
        {
            "type": "knx/get_entity_config",
            "entity_id": test_entity_id,
        }
    )
    res = await client.receive_json()
    assert res["success"], res
    assert res["result"] == {
        "platform": Platform.SWITCH,
        "unique_id": entity.unique_id,
        "data": {
            "entity": {
                "name": test_name,
                "device_info": None,
                "entity_category": None,
            },
            "knx": {
                "ga_switch": {"write": "1/2/3", "state": None, "passive": []},
                "invert": False,
                "respond_to_read": False,
                "sync_state": True,
            },
        },
        "schema_options": None,
    }


async def test_delete_entity(
    hass: HomeAssistant,
    knx: KNXTestKit,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test entity deletion."""
    await knx.setup_integration({})
    client = await hass_ws_client(hass)

    test_name = "Test no device"
    test_entity_id = "switch.test_no_device"
    assert not entity_registry.async_get(test_entity_id)

    # create entity
    await client.send_json_auto_id(
        {
            "type": "knx/create_entity",
            "platform": Platform.SWITCH,
            "data": {
                "entity": {"name": test_name},
                "knx": {"ga_switch": {"write": "1/2/3"}},
            },
        }
    )
    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["entity_id"] == test_entity_id
    assert entity_registry.async_get(test_entity_id)

    # delete entity
    await client.send_json_auto_id(
        {
            "type": "knx/delete_entity",
            "entity_id": test_entity_id,
        }
    )
    res = await client.receive_json()
    assert res["success"], res

    assert not entity_registry.async_get(test_entity_id)
    assert not hass_storage[KNX_CONFIG_STORAGE_KEY]["data"]["entities"].get("switch")


async def test_delete_entity_error(
    hass: HomeAssistant,
    knx: KNXTestKit,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test unsuccessful entity deletion."""
    await knx.setup_integration({})
    client = await hass_ws_client(hass)

    # delete unknown entity
    await client.send_json_auto_id(
        {
            "type": "knx/delete_entity",
            "entity_id": "switch.non_existing_entity",
        }
    )
    res = await client.receive_json()
    assert not res["success"], res
    assert res["error"]["code"] == "home_assistant_error"
    assert res["error"]["message"].startswith("Entity not found")

    # delete entity not in config store
    test_entity_id = "sensor.knx_interface_individual_address"
    assert entity_registry.async_get(test_entity_id)
    await client.send_json_auto_id(
        {
            "type": "knx/delete_entity",
            "entity_id": test_entity_id,
        }
    )
    res = await client.receive_json()
    assert not res["success"], res
    assert res["error"]["code"] == "home_assistant_error"
    assert res["error"]["message"].startswith("Entity not found")
