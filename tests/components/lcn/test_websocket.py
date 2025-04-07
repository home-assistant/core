"""LCN Websocket Tests."""

from typing import Any

from pypck.lcn_addr import LcnAddr
import pytest

from homeassistant.components.lcn import AddressType
from homeassistant.components.lcn.const import CONF_DOMAIN_DATA
from homeassistant.components.lcn.helpers import get_device_config, get_resource
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICES,
    CONF_DOMAIN,
    CONF_ENTITIES,
    CONF_NAME,
    CONF_RESOURCE,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant

from .conftest import MockConfigEntry, init_integration

from tests.typing import WebSocketGenerator

DEVICES_PAYLOAD = {CONF_TYPE: "lcn/devices", "entry_id": ""}
ENTITIES_PAYLOAD = {
    CONF_TYPE: "lcn/entities",
    "entry_id": "",
}
SCAN_PAYLOAD = {CONF_TYPE: "lcn/devices/scan", "entry_id": ""}
DEVICES_ADD_PAYLOAD = {
    CONF_TYPE: "lcn/devices/add",
    "entry_id": "",
    CONF_ADDRESS: (0, 10, False),
}
DEVICES_DELETE_PAYLOAD = {
    CONF_TYPE: "lcn/devices/delete",
    "entry_id": "",
    CONF_ADDRESS: (0, 7, False),
}
ENTITIES_ADD_PAYLOAD = {
    CONF_TYPE: "lcn/entities/add",
    "entry_id": "",
    CONF_ADDRESS: (0, 7, False),
    CONF_NAME: "test_switch",
    CONF_DOMAIN: "switch",
    CONF_DOMAIN_DATA: {"output": "RELAY5"},
}
ENTITIES_DELETE_PAYLOAD = {
    CONF_TYPE: "lcn/entities/delete",
    "entry_id": "",
    CONF_ADDRESS: (0, 7, False),
    CONF_DOMAIN: "switch",
    CONF_RESOURCE: "relay1",
}


async def test_lcn_devices_command(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, entry: MockConfigEntry
) -> None:
    """Test lcn/devices command."""
    await init_integration(hass, entry)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({**DEVICES_PAYLOAD, "entry_id": entry.entry_id})

    res = await client.receive_json()
    assert res["success"], res
    assert len(res["result"]) == len(entry.data[CONF_DEVICES])
    assert all(
        {**result, CONF_ADDRESS: tuple(result[CONF_ADDRESS])}
        in entry.data[CONF_DEVICES]
        for result in res["result"]
    )


@pytest.mark.parametrize(
    "payload",
    [
        ENTITIES_PAYLOAD,
        {**ENTITIES_PAYLOAD, CONF_ADDRESS: (0, 7, False)},
    ],
)
async def test_lcn_entities_command(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entry: MockConfigEntry,
    payload,
) -> None:
    """Test lcn/entities command."""
    await init_integration(hass, entry)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            **payload,
            "entry_id": entry.entry_id,
        }
    )

    res = await client.receive_json()
    assert res["success"], res
    entities = [
        entity
        for entity in entry.data[CONF_ENTITIES]
        if CONF_ADDRESS not in payload or entity[CONF_ADDRESS] == payload[CONF_ADDRESS]
    ]
    assert len(res["result"]) == len(entities)
    assert all(
        {**result, CONF_ADDRESS: tuple(result[CONF_ADDRESS])} in entities
        for result in res["result"]
    )


async def test_lcn_devices_scan_command(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, entry: MockConfigEntry
) -> None:
    """Test lcn/devices/scan command."""
    # add new module which is not stored in config_entry
    lcn_connection = await init_integration(hass, entry)
    lcn_connection.get_address_conn(LcnAddr(0, 10, False))

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({**SCAN_PAYLOAD, "entry_id": entry.entry_id})

    res = await client.receive_json()
    assert res["success"], res

    lcn_connection.scan_modules.assert_awaited()
    assert len(res["result"]) == len(entry.data[CONF_DEVICES])
    assert all(
        {**result, CONF_ADDRESS: tuple(result[CONF_ADDRESS])}
        in entry.data[CONF_DEVICES]
        for result in res["result"]
    )


async def test_lcn_devices_add_command(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, entry: MockConfigEntry
) -> None:
    """Test lcn/devices/add command."""
    await init_integration(hass, entry)

    client = await hass_ws_client(hass)
    assert get_device_config((0, 10, False), entry) is None

    await client.send_json_auto_id({**DEVICES_ADD_PAYLOAD, "entry_id": entry.entry_id})

    res = await client.receive_json()
    assert res["success"], res

    assert get_device_config((0, 10, False), entry)


async def test_lcn_devices_delete_command(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, entry: MockConfigEntry
) -> None:
    """Test lcn/devices/delete command."""
    await init_integration(hass, entry)

    client = await hass_ws_client(hass)
    assert get_device_config((0, 7, False), entry)

    await client.send_json_auto_id(
        {**DEVICES_DELETE_PAYLOAD, "entry_id": entry.entry_id}
    )

    res = await client.receive_json()
    assert res["success"], res
    assert get_device_config((0, 7, False), entry) is None


async def test_lcn_entities_add_command(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, entry: MockConfigEntry
) -> None:
    """Test lcn/entities/add command."""
    await init_integration(hass, entry)

    client = await hass_ws_client(hass)

    entity_config = {
        key: ENTITIES_ADD_PAYLOAD[key]
        for key in (CONF_ADDRESS, CONF_NAME, CONF_DOMAIN, CONF_DOMAIN_DATA)
    }

    resource = get_resource(
        ENTITIES_ADD_PAYLOAD[CONF_DOMAIN], ENTITIES_ADD_PAYLOAD[CONF_DOMAIN_DATA]
    ).lower()

    assert {**entity_config, CONF_RESOURCE: resource} not in entry.data[CONF_ENTITIES]

    await client.send_json_auto_id({**ENTITIES_ADD_PAYLOAD, "entry_id": entry.entry_id})

    res = await client.receive_json()
    assert res["success"], res

    assert {**entity_config, CONF_RESOURCE: resource} in entry.data[CONF_ENTITIES]


async def test_lcn_entities_delete_command(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, entry: MockConfigEntry
) -> None:
    """Test lcn/entities/delete command."""
    await init_integration(hass, entry)

    client = await hass_ws_client(hass)

    assert (
        len(
            [
                entity
                for entity in entry.data[CONF_ENTITIES]
                if entity[CONF_ADDRESS] == ENTITIES_DELETE_PAYLOAD[CONF_ADDRESS]
                and entity[CONF_DOMAIN] == ENTITIES_DELETE_PAYLOAD[CONF_DOMAIN]
                and entity[CONF_RESOURCE] == ENTITIES_DELETE_PAYLOAD[CONF_RESOURCE]
            ]
        )
        == 1
    )

    await client.send_json_auto_id(
        {**ENTITIES_DELETE_PAYLOAD, "entry_id": entry.entry_id}
    )

    res = await client.receive_json()
    assert res["success"], res

    assert (
        len(
            [
                entity
                for entity in entry.data[CONF_ENTITIES]
                if entity[CONF_ADDRESS] == ENTITIES_DELETE_PAYLOAD[CONF_ADDRESS]
                and entity[CONF_DOMAIN] == ENTITIES_DELETE_PAYLOAD[CONF_DOMAIN]
                and entity[CONF_RESOURCE] == ENTITIES_DELETE_PAYLOAD[CONF_RESOURCE]
            ]
        )
        == 0
    )


@pytest.mark.parametrize(
    ("payload", "entity_id", "result"),
    [
        (DEVICES_PAYLOAD, "12345", False),
        (ENTITIES_PAYLOAD, "12345", False),
        (SCAN_PAYLOAD, "12345", False),
        (DEVICES_ADD_PAYLOAD, "12345", False),
        (DEVICES_DELETE_PAYLOAD, "12345", False),
        (ENTITIES_ADD_PAYLOAD, "12345", False),
        (ENTITIES_DELETE_PAYLOAD, "12345", False),
    ],
)
async def test_lcn_command_host_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entry: MockConfigEntry,
    payload: dict[str, str],
    entity_id: str,
    result: bool,
) -> None:
    """Test lcn commands for unknown host."""
    await init_integration(hass, entry)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({**payload, "entry_id": entity_id})

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"] == result


@pytest.mark.parametrize(
    ("payload", "address", "result"),
    [
        (DEVICES_ADD_PAYLOAD, (0, 7, False), False),  # device already existing
        (DEVICES_DELETE_PAYLOAD, (0, 42, False), False),
        (ENTITIES_ADD_PAYLOAD, (0, 42, False), False),
        (ENTITIES_DELETE_PAYLOAD, (0, 42, 0), False),
    ],
)
async def test_lcn_command_address_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entry: MockConfigEntry,
    payload: dict[str, Any],
    address: AddressType,
    result: bool,
) -> None:
    """Test lcn commands for address error."""
    await init_integration(hass, entry)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {**payload, "entry_id": entry.entry_id, CONF_ADDRESS: address}
    )

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"] == result


async def test_lcn_entities_add_existing_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entry: MockConfigEntry,
) -> None:
    """Test lcn commands for address error."""
    await init_integration(hass, entry)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            **ENTITIES_ADD_PAYLOAD,
            "entry_id": entry.entry_id,
            CONF_DOMAIN_DATA: {"output": "RELAY1"},
        }
    )

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"] is False
