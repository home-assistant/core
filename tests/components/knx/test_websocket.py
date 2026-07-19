"""KNX Websocket Tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from knx_telegram_store import KnxTelegramStoreException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.knx.const import (
    CONF_KNX_TELEGRAM_DB_BACKEND,
    CONF_KNX_TELEGRAM_DB_POSTGRES_DSN,
    KNX_ADDRESS,
    KNX_MODULE_KEY,
    KNX_TELEGRAM_BACKEND_POSTGRES,
    SUPPORTED_PLATFORMS_UI,
)
from homeassistant.components.knx.project import STORAGE_KEY as KNX_PROJECT_STORAGE_KEY
from homeassistant.components.knx.schema import SwitchSchema
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from .conftest import KNXTestKit

from tests.typing import WebSocketGenerator


async def test_knx_get_base_data_command(
    hass: HomeAssistant, knx: KNXTestKit, hass_ws_client: WebSocketGenerator
) -> None:
    """Test knx/get_base_data command."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "knx/get_base_data"})

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["connection_info"]["version"] is not None
    assert res["result"]["connection_info"]["connected"]
    assert res["result"]["connection_info"]["current_address"] == "0.0.0"
    assert res["result"]["connection_info"]["telegram_backend"] == "sqlite"
    assert res["result"]["project_info"] is None
    assert not SUPPORTED_PLATFORMS_UI.difference(res["result"]["supported_platforms"])


async def test_knx_get_base_data_command_postgres(
    hass: HomeAssistant, knx: KNXTestKit, hass_ws_client: WebSocketGenerator
) -> None:
    """Test knx/get_base_data reports the PostgreSQL telegram backend."""
    knx.mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        knx.mock_config_entry,
        options=knx.mock_config_entry.options
        | {
            CONF_KNX_TELEGRAM_DB_BACKEND: KNX_TELEGRAM_BACKEND_POSTGRES,
            CONF_KNX_TELEGRAM_DB_POSTGRES_DSN: "postgresql://user:pw@db.local:5432/knx",
        },
    )
    # Patch methods on the real class so the isinstance check in the
    # websocket handler still sees a BufferedPostgresStore instance.
    with (
        patch(
            "knx_telegram_store.BufferedPostgresStore.needs_migration",
            return_value=False,
        ),
        patch("knx_telegram_store.BufferedPostgresStore.initialize"),
        patch(
            "knx_telegram_store.BufferedPostgresStore.get_last_unique_telegrams",
            return_value=[],
        ),
    ):
        await knx.setup_integration(add_entry_to_hass=False)
        client = await hass_ws_client(hass)
        await client.send_json_auto_id({"type": "knx/get_base_data"})
        res = await client.receive_json()

    assert res["success"], res
    assert res["result"]["connection_info"]["telegram_backend"] == "postgres"


@pytest.mark.usefixtures("load_knxproj")
async def test_knx_get_base_data_command_with_project(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test knx/get_base_data command with loaded project."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "knx/get_base_data"})

    res = await client.receive_json()
    assert res["success"], res

    connection_info = res["result"]["connection_info"]
    assert connection_info["version"] is not None
    assert connection_info["connected"]
    assert connection_info["current_address"] == "0.0.0"

    project_info = res["result"]["project_info"]
    assert project_info is not None
    assert project_info["name"] == "Fixture"
    assert project_info["last_modified"] == "2023-04-30T09:04:04.4043671Z"
    assert project_info["tool_version"] == "5.7.1428.39779"


async def test_knx_project_file_process(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    project_data: dict[str, Any],
) -> None:
    """Test knx/project_file_process command for storing and loading new data."""
    _file_id = "1234"
    _password = "pw-test"

    await knx.setup_integration()
    client = await hass_ws_client(hass)
    assert not hass.data[KNX_MODULE_KEY].project.loaded

    await client.send_json_auto_id(
        {
            "type": "knx/project_file_process",
            "file_id": _file_id,
            "password": _password,
        }
    )
    with (
        patch(
            "homeassistant.components.knx.project.process_uploaded_file",
        ) as file_upload_mock,
        patch("xknxproject.XKNXProj.parse", return_value=project_data) as parse_mock,
    ):
        file_upload_mock.return_value.__enter__.return_value = ""
        res = await client.receive_json()

        file_upload_mock.assert_called_once_with(hass, _file_id)
        parse_mock.assert_called_once_with()

    assert res["success"], res
    assert hass.data[KNX_MODULE_KEY].project.loaded
    assert hass_storage[KNX_PROJECT_STORAGE_KEY]["data"] == project_data


async def test_knx_project_file_process_error(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test knx/project_file_process exception handling."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)
    assert not hass.data[KNX_MODULE_KEY].project.loaded

    await client.send_json_auto_id(
        {
            "type": "knx/project_file_process",
            "file_id": "1234",
            "password": "",
        }
    )
    with (
        patch(
            "homeassistant.components.knx.project.process_uploaded_file",
        ) as file_upload_mock,
        patch("xknxproject.XKNXProj.parse", side_effect=ValueError) as parse_mock,
    ):
        file_upload_mock.return_value.__enter__.return_value = ""
        res = await client.receive_json()
        parse_mock.assert_called_once_with()

    assert res["error"], res
    assert not hass.data[KNX_MODULE_KEY].project.loaded


@pytest.mark.usefixtures("load_knxproj")
async def test_knx_project_file_remove(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test knx/project_file_remove command."""
    await knx.setup_integration()
    assert hass_storage[KNX_PROJECT_STORAGE_KEY]
    client = await hass_ws_client(hass)
    assert hass.data[KNX_MODULE_KEY].project.loaded

    await client.send_json_auto_id({"type": "knx/project_file_remove"})
    res = await client.receive_json()

    assert res["success"], res
    assert not hass.data[KNX_MODULE_KEY].project.loaded
    assert not hass_storage.get(KNX_PROJECT_STORAGE_KEY)


@pytest.mark.usefixtures("load_knxproj")
async def test_knx_get_project(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    project_data: dict[str, Any],
) -> None:
    """Test retrieval of kxnproject from store."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)
    assert hass.data[KNX_MODULE_KEY].project.loaded

    await client.send_json_auto_id({"type": "knx/get_knx_project"})
    res = await client.receive_json()
    assert res["success"], res
    assert res["result"] == project_data


async def test_knx_get_project_no_project(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    project_data: dict[str, Any],
) -> None:
    """Test retrieval of kxnproject from store."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)
    assert not hass.data[KNX_MODULE_KEY].project.loaded

    await client.send_json_auto_id({"type": "knx/get_knx_project"})
    res = await client.receive_json()
    assert res["success"], res
    assert res["result"] is None


async def test_knx_group_monitor_info_command(
    hass: HomeAssistant, knx: KNXTestKit, hass_ws_client: WebSocketGenerator
) -> None:
    """Test knx/group_monitor_info command."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "knx/group_monitor_info"})

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["project_loaded"] is False
    assert res["result"]["recent_telegrams"] == []


async def test_knx_query_telegrams_command(
    hass: HomeAssistant, knx: KNXTestKit, hass_ws_client: WebSocketGenerator
) -> None:
    """Test knx/query_telegrams command."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)

    # get some telegrams to populate the store
    await knx.receive_write("1/1/1", True)
    await knx.receive_write("2/2/2", (1, 2, 3))
    await knx.receive_write("3/3/3", 0x34)
    # wait for async store task; the websocket handler flushes buffered
    # telegrams before querying, so no explicit flush is needed here
    await hass.async_block_till_done()

    # Query all
    await client.send_json_auto_id({"type": "knx/query_telegrams"})
    res = await client.receive_json()
    assert res["success"], res
    assert len(res["result"]["telegrams"]) == 3
    assert res["result"]["total_count"] == 3
    assert res["result"]["limit_reached"] is False

    # Query with filter
    await client.send_json_auto_id(
        {
            "type": "knx/query_telegrams",
            "destinations": ["1/1/1", "3/3/3"],
        }
    )
    res = await client.receive_json()
    assert res["success"], res
    assert len(res["result"]["telegrams"]) == 2
    assert res["result"]["total_count"] == 2

    # Query with limit
    await client.send_json_auto_id(
        {
            "type": "knx/query_telegrams",
            "limit": 1,
        }
    )
    res = await client.receive_json()
    assert res["success"], res
    assert len(res["result"]["telegrams"]) == 1
    assert res["result"]["total_count"] == 3
    assert res["result"]["limit_reached"] is True


@pytest.mark.parametrize(
    "command",
    ["knx/group_monitor_info", "knx/query_telegrams"],
)
async def test_telegram_store_not_initialized(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    command: str,
) -> None:
    """Test telegram commands when the storage backend failed to initialize."""
    # Force initialization to fail so the store stays uninitialized (None)
    with patch(
        "knx_telegram_store.BufferedSqliteStore.initialize",
        side_effect=KnxTelegramStoreException("init failed"),
    ):
        await knx.setup_integration()
    client = await hass_ws_client(hass)

    assert hass.data[KNX_MODULE_KEY].telegrams.store is None

    await client.send_json_auto_id({"type": command})
    res = await client.receive_json()
    assert not res["success"]
    assert "not initialized" in res["error"]["message"]


@pytest.mark.parametrize(
    "command",
    ["knx/group_monitor_info", "knx/query_telegrams"],
)
async def test_telegram_store_query_database_error(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    command: str,
) -> None:
    """Test telegram commands when the store query raises a database error."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)

    store = hass.data[KNX_MODULE_KEY].telegrams.store
    assert store is not None
    with patch.object(store, "query", side_effect=KnxTelegramStoreException("boom")):
        await client.send_json_auto_id({"type": command})
        res = await client.receive_json()
    assert not res["success"]
    assert "Database error" in res["error"]["message"]


async def test_knx_group_telegrams_command(
    hass: HomeAssistant, knx: KNXTestKit, hass_ws_client: WebSocketGenerator
) -> None:
    """Test knx/group_telegrams command."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "knx/group_telegrams"})
    res = await client.receive_json()
    assert res["success"], res
    assert res["result"] == {}

    # # get some telegrams to populate the cache
    await knx.receive_write("1/1/1", True)
    await knx.receive_read("2/2/2")  # read telegram shall be ignored
    await knx.receive_write("3/3/3", 0x34)

    await client.send_json_auto_id({"type": "knx/group_telegrams"})
    res = await client.receive_json()
    assert res["success"], res
    assert len(res["result"]) == 2
    assert "1/1/1" in res["result"]
    assert res["result"]["1/1/1"]["destination"] == "1/1/1"
    assert "3/3/3" in res["result"]
    assert res["result"]["3/3/3"]["payload"] == 52
    assert res["result"]["3/3/3"]["telegramtype"] == "GroupValueWrite"
    assert res["result"]["3/3/3"]["source"] == "1.2.3"
    assert res["result"]["3/3/3"]["direction"] == "Incoming"
    assert res["result"]["3/3/3"]["timestamp"] is not None


async def test_knx_subscribe_telegrams_command_recent_telegrams(
    hass: HomeAssistant, knx: KNXTestKit, hass_ws_client: WebSocketGenerator
) -> None:
    """Test knx/subscribe_telegrams command sending recent telegrams."""
    await knx.setup_integration(
        {
            SwitchSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: "1/2/4",
            }
        }
    )

    # send incoming telegram
    await knx.receive_write("1/3/4", True)
    # send outgoing telegram
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.test"}, blocking=True
    )
    await knx.assert_write("1/2/4", 1)

    # wait for async store task; group_monitor_info flushes buffered telegrams
    # before querying, so no explicit flush is needed here
    await hass.async_block_till_done()

    # connect websocket after telegrams have been sent
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "knx/group_monitor_info"})
    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["project_loaded"] is False

    recent_tgs = res["result"]["recent_telegrams"]
    assert len(recent_tgs) == 2
    # telegrams are sorted from newest to oldest
    assert recent_tgs[0]["destination"] == "1/2/4"
    assert recent_tgs[0]["payload"] == 1
    assert recent_tgs[0]["telegramtype"] == "GroupValueWrite"
    assert (
        recent_tgs[0]["source"] == "0.0.0"
    )  # needs to be the IA currently connected to
    assert recent_tgs[0]["direction"] == "Outgoing"
    assert isinstance(recent_tgs[0]["timestamp"], str)

    assert recent_tgs[1]["destination"] == "1/3/4"
    assert recent_tgs[1]["payload"] == 1
    assert recent_tgs[1]["telegramtype"] == "GroupValueWrite"
    assert recent_tgs[1]["source"] == "1.2.3"
    assert recent_tgs[1]["direction"] == "Incoming"
    assert isinstance(recent_tgs[1]["timestamp"], str)


async def test_knx_subscribe_telegrams_command_no_project(
    hass: HomeAssistant, knx: KNXTestKit, hass_ws_client: WebSocketGenerator
) -> None:
    """Test knx/subscribe_telegrams command without project data."""
    await knx.setup_integration(
        {
            SwitchSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: "1/2/4",
            }
        }
    )
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "knx/subscribe_telegrams"})
    res = await client.receive_json()
    assert res["success"], res

    # send incoming telegrams
    await knx.receive_read("1/2/3")
    await knx.receive_write("1/3/4", True)
    await knx.receive_write("1/3/4", False)
    await knx.receive_write("1/3/8", (0x34, 0x45))
    # send outgoing telegrams
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.test"}, blocking=True
    )
    await knx.assert_write("1/2/4", 1)
    # receive undecodable data secure telegram
    knx.receive_data_secure_issue("1/2/5")

    # receive events
    res = await client.receive_json()
    assert res["event"]["destination"] == "1/2/3"
    assert res["event"]["payload"] is None
    assert res["event"]["telegramtype"] == "GroupValueRead"
    assert res["event"]["source"] == "1.2.3"
    assert res["event"]["direction"] == "Incoming"
    assert res["event"]["timestamp"] is not None

    res = await client.receive_json()
    assert res["event"]["destination"] == "1/3/4"
    assert res["event"]["payload"] == 1
    assert res["event"]["telegramtype"] == "GroupValueWrite"
    assert res["event"]["source"] == "1.2.3"
    assert res["event"]["direction"] == "Incoming"
    assert res["event"]["timestamp"] is not None

    res = await client.receive_json()
    assert res["event"]["destination"] == "1/3/4"
    assert res["event"]["payload"] == 0
    assert res["event"]["telegramtype"] == "GroupValueWrite"
    assert res["event"]["source"] == "1.2.3"
    assert res["event"]["direction"] == "Incoming"
    assert res["event"]["timestamp"] is not None

    res = await client.receive_json()
    assert res["event"]["destination"] == "1/3/8"
    assert res["event"]["payload"] == [52, 69]
    assert res["event"]["telegramtype"] == "GroupValueWrite"
    assert res["event"]["source"] == "1.2.3"
    assert res["event"]["direction"] == "Incoming"
    assert res["event"]["timestamp"] is not None

    res = await client.receive_json()
    assert res["event"]["destination"] == "1/2/4"
    assert res["event"]["payload"] == 1
    assert res["event"]["telegramtype"] == "GroupValueWrite"
    assert (
        res["event"]["source"] == "0.0.0"
    )  # needs to be the IA currently connected to
    assert res["event"]["direction"] == "Outgoing"
    assert res["event"]["timestamp"] is not None

    res = await client.receive_json()
    assert res["event"]["destination"] == "1/2/5"
    assert res["event"]["payload"] is None
    assert res["event"]["telegramtype"] == "SecureAPDU"
    assert res["event"]["source"] == "1.2.3"
    assert res["event"]["direction"] == "Incoming"
    assert res["event"]["timestamp"] is not None


async def test_knx_subscribe_telegrams_command_project(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    load_knxproj: None,
) -> None:
    """Test knx/subscribe_telegrams command with project data."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "knx/subscribe_telegrams"})
    res = await client.receive_json()
    assert res["success"], res

    # incoming DPT 1 telegram
    await knx.receive_write("0/0/1", True)
    res = await client.receive_json()
    assert res["event"]["destination"] == "0/0/1"
    assert res["event"]["destination_name"] == "Binary"
    assert res["event"]["payload"] == 1
    assert res["event"]["telegramtype"] == "GroupValueWrite"
    assert res["event"]["source"] == "1.2.3"
    assert res["event"]["direction"] == "Incoming"
    assert res["event"]["timestamp"] is not None

    # incoming DPT 5 telegram
    await knx.receive_write("0/1/1", (0x50,), source="1.1.6")
    res = await client.receive_json()
    assert res["event"]["destination"] == "0/1/1"
    assert res["event"]["destination_name"] == "percent"
    assert res["event"]["payload"] == [
        80,
    ]
    assert res["event"]["value"] == 31
    assert res["event"]["unit"] == "%"
    assert res["event"]["telegramtype"] == "GroupValueWrite"
    assert res["event"]["source"] == "1.1.6"
    assert (
        res["event"]["source_name"]
        == "Enertex Bayern GmbH Enertex KNX LED Dimmsequenzer 20A/5x REG"
    )
    assert res["event"]["direction"] == "Incoming"
    assert res["event"]["timestamp"] is not None

    # incoming undecodable telegram (wrong payload type)
    await knx.receive_write("0/1/1", True, source="1.1.6")
    res = await client.receive_json()
    assert res["event"]["destination"] == "0/1/1"
    assert res["event"]["destination_name"] == "percent"
    assert res["event"]["payload"] == 1
    assert res["event"]["value"] is None
    assert res["event"]["telegramtype"] == "GroupValueWrite"
    assert res["event"]["source"] == "1.1.6"
    assert (
        res["event"]["source_name"]
        == "Enertex Bayern GmbH Enertex KNX LED Dimmsequenzer 20A/5x REG"
    )
    assert res["event"]["direction"] == "Incoming"
    assert res["event"]["timestamp"] is not None


@pytest.mark.parametrize("platform", sorted({*SUPPORTED_PLATFORMS_UI, "tts"}))
async def test_knx_get_schema(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    platform: str,
) -> None:
    """Test knx/get_schema command returning proper schema data."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "knx/get_schema", "platform": platform})
    res = await client.receive_json()
    assert res == snapshot


async def test_knx_get_expose_groups(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test knx/get_expose_groups command returning proper expose groups data."""
    await knx.setup_integration(
        config_store_fixture="config_store_expose.json",
    )
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "knx/get_expose_groups"})
    res = await client.receive_json()
    assert res == snapshot


async def test_knx_get_expose_config(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test knx/get_expose_config command returning proper expose config data."""
    await knx.setup_integration(
        config_store_fixture="config_store_expose.json",
    )
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "knx/get_expose_config",
            "entity_id": "cover.test",
        }
    )
    res = await client.receive_json()
    assert res == snapshot


@pytest.mark.parametrize(
    "endpoint",
    [
        "knx/get_base_data",  # sync ws-command
        "knx/get_knx_project",  # async ws-command
    ],
)
async def test_websocket_when_config_entry_unloaded(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    endpoint: str,
) -> None:
    """Test websocket connection when config entry is unloaded."""
    await knx.setup_integration()
    await hass.config_entries.async_unload(knx.mock_config_entry.entry_id)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": endpoint})
    res = await client.receive_json()
    assert not res["success"]
    assert res["error"]["code"] == "home_assistant_error"
    assert res["error"]["message"] == "KNX integration not loaded."
