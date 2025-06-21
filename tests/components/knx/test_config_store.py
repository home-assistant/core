"""Test KNX config store."""

from typing import Any

import pytest

from homeassistant.components.knx.storage.config_store import (
    STORAGE_KEY as KNX_CONFIG_STORAGE_KEY,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import KnxEntityGenerator
from .conftest import KNXTestKit

from tests.typing import WebSocketGenerator


async def test_create_entity(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    create_ui_entity: KnxEntityGenerator,
) -> None:
    """Test entity creation."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)

    test_name = "Test no device"
    test_entity = await create_ui_entity(
        platform=Platform.SWITCH,
        knx_data={"ga_switch": {"write": "1/2/3"}},
        entity_data={"name": test_name},
    )

    # Test if entity is correctly stored in registry
    await client.send_json_auto_id({"type": "knx/get_entity_entries"})
    res = await client.receive_json()
    assert res["success"], res
    assert res["result"] == [
        test_entity.extended_dict,
    ]
    # Test if entity is correctly stored in config store
    test_storage_data = next(
        iter(
            hass_storage[KNX_CONFIG_STORAGE_KEY]["data"]["entities"]["switch"].values()
        )
    )
    assert test_storage_data == {
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
    }


async def test_create_entity_error(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test unsuccessful entity creation."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)

    # create entity with invalid platform
    await client.send_json_auto_id(
        {
            "type": "knx/create_entity",
            "platform": "invalid_platform",
            "data": {
                "entity": {"name": "Test invalid platform"},
                "knx": {"ga_switch": {"write": "1/2/3"}},
            },
        }
    )
    res = await client.receive_json()
    assert res["success"], res
    assert not res["result"]["success"]
    assert res["result"]["errors"][0]["path"] == ["platform"]
    assert res["result"]["error_base"].startswith("expected Platform or one of")

    # create entity with unsupported platform
    await client.send_json_auto_id(
        {
            "type": "knx/create_entity",
            "platform": Platform.TTS,  # "tts" is not a supported platform (and is unlikely to ever be)
            "data": {
                "entity": {"name": "Test invalid platform"},
                "knx": {"ga_switch": {"write": "1/2/3"}},
            },
        }
    )
    res = await client.receive_json()
    assert res["success"], res
    assert not res["result"]["success"]
    assert res["result"]["errors"][0]["path"] == ["platform"]
    assert res["result"]["error_base"].startswith("value must be one of")


async def test_update_entity(
    hass: HomeAssistant,
    knx: KNXTestKit,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    create_ui_entity: KnxEntityGenerator,
) -> None:
    """Test entity update."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)

    test_entity = await create_ui_entity(
        platform=Platform.SWITCH,
        knx_data={"ga_switch": {"write": "1/2/3"}},
        entity_data={"name": "Test"},
    )
    test_entity_id = test_entity.entity_id

    # update entity
    new_name = "Updated name"
    new_ga_switch_write = "4/5/6"
    await client.send_json_auto_id(
        {
            "type": "knx/update_entity",
            "platform": Platform.SWITCH,
            "entity_id": test_entity_id,
            "data": {
                "entity": {"name": new_name},
                "knx": {"ga_switch": {"write": new_ga_switch_write}},
            },
        }
    )
    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["success"]

    entity = entity_registry.async_get(test_entity_id)
    assert entity
    assert entity.original_name == new_name

    assert (
        hass_storage[KNX_CONFIG_STORAGE_KEY]["data"]["entities"]["switch"][
            test_entity.unique_id
        ]["knx"]["ga_switch"]["write"]
        == new_ga_switch_write
    )


async def test_update_entity_error(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    create_ui_entity: KnxEntityGenerator,
) -> None:
    """Test entity update."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)

    test_entity = await create_ui_entity(
        platform=Platform.SWITCH,
        knx_data={"ga_switch": {"write": "1/2/3"}},
        entity_data={"name": "Test"},
    )

    # update unsupported platform
    new_name = "Updated name"
    new_ga_switch_write = "4/5/6"
    await client.send_json_auto_id(
        {
            "type": "knx/update_entity",
            "platform": Platform.TTS,
            "entity_id": test_entity.entity_id,
            "data": {
                "entity": {"name": new_name},
                "knx": {"ga_switch": {"write": new_ga_switch_write}},
            },
        }
    )
    res = await client.receive_json()
    assert res["success"], res
    assert not res["result"]["success"]
    assert res["result"]["errors"][0]["path"] == ["platform"]
    assert res["result"]["error_base"].startswith("value must be one of")

    # entity not found
    await client.send_json_auto_id(
        {
            "type": "knx/update_entity",
            "platform": Platform.SWITCH,
            "entity_id": "non_existing_entity_id",
            "data": {
                "entity": {"name": new_name},
                "knx": {"ga_switch": {"write": new_ga_switch_write}},
            },
        }
    )
    res = await client.receive_json()
    assert not res["success"], res
    assert res["error"]["code"] == "home_assistant_error"
    assert res["error"]["message"].startswith("Entity not found:")

    # entity not in storage
    await client.send_json_auto_id(
        {
            "type": "knx/update_entity",
            "platform": Platform.SWITCH,
            # `sensor` isn't yet supported, but we only have sensor entities automatically
            # created with no configuration - it doesn't ,atter for the test though
            "entity_id": "sensor.knx_interface_individual_address",
            "data": {
                "entity": {"name": new_name},
                "knx": {"ga_switch": {"write": new_ga_switch_write}},
            },
        }
    )
    res = await client.receive_json()
    assert not res["success"], res
    assert res["error"]["code"] == "home_assistant_error"
    assert res["error"]["message"].startswith("Entity not found in storage")


async def test_delete_entity(
    hass: HomeAssistant,
    knx: KNXTestKit,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    create_ui_entity: KnxEntityGenerator,
) -> None:
    """Test entity deletion."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)

    test_entity = await create_ui_entity(
        platform=Platform.SWITCH,
        knx_data={"ga_switch": {"write": "1/2/3"}},
        entity_data={"name": "Test"},
    )
    test_entity_id = test_entity.entity_id

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
    await knx.setup_integration()
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


async def test_get_entity_config(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    create_ui_entity: KnxEntityGenerator,
) -> None:
    """Test entity config retrieval."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)

    test_entity = await create_ui_entity(
        platform=Platform.SWITCH,
        knx_data={"ga_switch": {"write": "1/2/3"}},
        entity_data={"name": "Test"},
    )

    await client.send_json_auto_id(
        {
            "type": "knx/get_entity_config",
            "entity_id": test_entity.entity_id,
        }
    )
    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["platform"] == Platform.SWITCH
    assert res["result"]["data"] == {
        "entity": {
            "name": "Test",
            "device_info": None,
            "entity_category": None,
        },
        "knx": {
            "ga_switch": {"write": "1/2/3", "passive": [], "state": None},
            "respond_to_read": False,
            "invert": False,
            "sync_state": True,
        },
    }


@pytest.mark.parametrize(
    ("test_entity_id", "error_message_start"),
    [
        ("switch.non_existing_entity", "Entity not found"),
        ("sensor.knx_interface_individual_address", "Entity data not found"),
    ],
)
async def test_get_entity_config_error(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    test_entity_id: str,
    error_message_start: str,
) -> None:
    """Test entity config retrieval errors."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "knx/get_entity_config",
            "entity_id": test_entity_id,
        }
    )
    res = await client.receive_json()
    assert not res["success"], res
    assert res["error"]["code"] == "home_assistant_error"
    assert res["error"]["message"].startswith(error_message_start)


async def test_validate_entity(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test entity validation."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "knx/validate_entity",
            "platform": Platform.SWITCH,
            "data": {
                "entity": {"name": "test_name"},
                "knx": {"ga_switch": {"write": "1/2/3"}},
            },
        }
    )
    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["success"] is True

    # invalid data
    await client.send_json_auto_id(
        {
            "type": "knx/validate_entity",
            "platform": Platform.SWITCH,
            "data": {
                "entity": {"name": "test_name"},
                "knx": {"ga_switch": {}},
            },
        }
    )
    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["success"] is False
    assert res["result"]["errors"][0]["path"] == ["data", "knx", "ga_switch", "write"]
    assert res["result"]["errors"][0]["error_message"] == "required key not provided"
    assert res["result"]["error_base"].startswith("required key not provided")
