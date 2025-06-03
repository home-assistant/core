"""KNX Websocket Tests."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.knx.const import KNX_ADDRESS, KNX_MODULE_KEY
from homeassistant.components.knx.project import STORAGE_KEY as KNX_PROJECT_STORAGE_KEY
from homeassistant.components.knx.schema import SwitchSchema
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from .conftest import FIXTURE_PROJECT_DATA, KNXTestKit

from tests.typing import WebSocketGenerator


async def test_knx_info_command(
    hass: HomeAssistant, knx: KNXTestKit, hass_ws_client: WebSocketGenerator
) -> None:
    """Test knx/info command."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)
    await client.send_json({"id": 6, "type": "knx/info"})

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["version"] is not None
    assert res["result"]["connected"]
    assert res["result"]["current_address"] == "0.0.0"
    assert res["result"]["project"] is None


async def test_knx_info_command_with_project(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    load_knxproj: None,
) -> None:
    """Test knx/info command with loaded project."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)
    await client.send_json({"id": 6, "type": "knx/info"})

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["version"] is not None
    assert res["result"]["connected"]
    assert res["result"]["current_address"] == "0.0.0"
    assert res["result"]["project"] is not None
    assert res["result"]["project"]["name"] == "Fixture"
    assert res["result"]["project"]["last_modified"] == "2023-04-30T09:04:04.4043671Z"
    assert res["result"]["project"]["tool_version"] == "5.7.1428.39779"


async def test_knx_project_file_process(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test knx/project_file_process command for storing and loading new data."""
    _file_id = "1234"
    _password = "pw-test"
    _parse_result = FIXTURE_PROJECT_DATA

    await knx.setup_integration()
    client = await hass_ws_client(hass)
    assert not hass.data[KNX_MODULE_KEY].project.loaded

    await client.send_json(
        {
            "id": 6,
            "type": "knx/project_file_process",
            "file_id": _file_id,
            "password": _password,
        }
    )
    with (
        patch(
            "homeassistant.components.knx.project.process_uploaded_file",
        ) as file_upload_mock,
        patch("xknxproject.XKNXProj.parse", return_value=_parse_result) as parse_mock,
    ):
        file_upload_mock.return_value.__enter__.return_value = ""
        res = await client.receive_json()

        file_upload_mock.assert_called_once_with(hass, _file_id)
        parse_mock.assert_called_once_with()

    assert res["success"], res
    assert hass.data[KNX_MODULE_KEY].project.loaded
    assert hass_storage[KNX_PROJECT_STORAGE_KEY]["data"] == _parse_result


async def test_knx_project_file_process_error(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test knx/project_file_process exception handling."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)
    assert not hass.data[KNX_MODULE_KEY].project.loaded

    await client.send_json(
        {
            "id": 6,
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


async def test_knx_project_file_remove(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    load_knxproj: None,
    hass_storage: dict[str, Any],
) -> None:
    """Test knx/project_file_remove command."""
    await knx.setup_integration()
    assert hass_storage[KNX_PROJECT_STORAGE_KEY]
    client = await hass_ws_client(hass)
    assert hass.data[KNX_MODULE_KEY].project.loaded

    await client.send_json({"id": 6, "type": "knx/project_file_remove"})
    res = await client.receive_json()

    assert res["success"], res
    assert not hass.data[KNX_MODULE_KEY].project.loaded
    assert not hass_storage.get(KNX_PROJECT_STORAGE_KEY)


async def test_knx_get_project(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    load_knxproj: None,
) -> None:
    """Test retrieval of kxnproject from store."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)
    assert hass.data[KNX_MODULE_KEY].project.loaded

    await client.send_json({"id": 3, "type": "knx/get_knx_project"})
    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["project_loaded"] is True
    assert res["result"]["knxproject"] == FIXTURE_PROJECT_DATA


async def test_knx_group_monitor_info_command(
    hass: HomeAssistant, knx: KNXTestKit, hass_ws_client: WebSocketGenerator
) -> None:
    """Test knx/group_monitor_info command."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)

    await client.send_json({"id": 6, "type": "knx/group_monitor_info"})

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["project_loaded"] is False
    assert res["result"]["recent_telegrams"] == []


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

    # connect websocket after telegrams have been sent
    client = await hass_ws_client(hass)
    await client.send_json({"id": 6, "type": "knx/group_monitor_info"})
    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["project_loaded"] is False

    recent_tgs = res["result"]["recent_telegrams"]
    assert len(recent_tgs) == 2
    # telegrams are sorted from oldest to newest
    assert recent_tgs[0]["destination"] == "1/3/4"
    assert recent_tgs[0]["payload"] == 1
    assert recent_tgs[0]["telegramtype"] == "GroupValueWrite"
    assert recent_tgs[0]["source"] == "1.2.3"
    assert recent_tgs[0]["direction"] == "Incoming"
    assert isinstance(recent_tgs[0]["timestamp"], str)

    assert recent_tgs[1]["destination"] == "1/2/4"
    assert recent_tgs[1]["payload"] == 1
    assert recent_tgs[1]["telegramtype"] == "GroupValueWrite"
    assert (
        recent_tgs[1]["source"] == "0.0.0"
    )  # needs to be the IA currently connected to
    assert recent_tgs[1]["direction"] == "Outgoing"
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
    await client.send_json({"id": 6, "type": "knx/subscribe_telegrams"})
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


async def test_knx_subscribe_telegrams_command_project(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    load_knxproj: None,
) -> None:
    """Test knx/subscribe_telegrams command with project data."""
    await knx.setup_integration()
    client = await hass_ws_client(hass)
    await client.send_json({"id": 6, "type": "knx/subscribe_telegrams"})
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


@pytest.mark.parametrize(
    "endpoint",
    [
        "knx/info",  # sync ws-command
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
