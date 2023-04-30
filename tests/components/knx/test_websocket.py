"""KNX Websocket Tests."""
import json
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.knx import DOMAIN, KNX_ADDRESS, SwitchSchema
from homeassistant.components.knx.project import STORAGE_KEY as KNX_PROJECT_STORAGE_KEY
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from .conftest import KNXTestKit

from tests.common import load_fixture
from tests.typing import WebSocketGenerator

FIXTURE_PROJECT_DATA = json.loads(load_fixture("project.json", DOMAIN))


@pytest.fixture(name="load_knxproj")
def fixture_load_project(hass_storage):
    """Mock KNX project data."""
    hass_storage[KNX_PROJECT_STORAGE_KEY] = {
        "version": 1,
        "data": FIXTURE_PROJECT_DATA,
    }
    return


async def test_knx_info_command(
    hass: HomeAssistant, knx: KNXTestKit, hass_ws_client: WebSocketGenerator
):
    """Test knx/info command."""
    await knx.setup_integration({})

    client = await hass_ws_client(hass)

    await client.send_json({"id": 6, "type": "knx/info"})

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["version"] is not None
    assert res["result"]["connected"]
    assert res["result"]["current_address"] == "0.0.0"
    assert res["result"]["project"] is None


async def test_knx_project_file_process(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
):
    """Test knx/project_file_process command for storing and loading new data."""
    _file_id = "1234"
    _password = "pw-test"
    _parse_result = FIXTURE_PROJECT_DATA

    await knx.setup_integration({})
    client = await hass_ws_client(hass)
    assert not hass.data[DOMAIN].project.loaded

    await client.send_json(
        {
            "id": 6,
            "type": "knx/project_file_process",
            "file_id": _file_id,
            "password": _password,
        }
    )
    with patch(
        "homeassistant.components.knx.project.process_uploaded_file",
    ) as file_upload_mock, patch(
        "xknxproject.XKNXProj.parse", return_value=_parse_result
    ) as parse_mock:
        file_upload_mock.return_value.__enter__.return_value = ""
        res = await client.receive_json()

        file_upload_mock.assert_called_once_with(hass, _file_id)
        parse_mock.assert_called_once_with()

    assert res["success"], res
    assert hass.data[DOMAIN].project.loaded


async def test_knx_project_file_remove(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    load_knxproj,
):
    """Test knx/project_file_remove command."""
    await knx.setup_integration({})
    client = await hass_ws_client(hass)
    assert hass.data[DOMAIN].project.loaded

    await client.send_json({"id": 6, "type": "knx/project_file_remove"})
    with patch("homeassistant.helpers.storage.Store.async_remove") as remove_mock:
        res = await client.receive_json()
        remove_mock.assert_called_once_with()

    assert res["success"], res
    assert not hass.data[DOMAIN].project.loaded


async def test_knx_group_monitor_info_command(
    hass: HomeAssistant, knx: KNXTestKit, hass_ws_client: WebSocketGenerator
):
    """Test knx/group_monitor_info command."""
    await knx.setup_integration({})
    client = await hass_ws_client(hass)

    await client.send_json({"id": 6, "type": "knx/group_monitor_info"})

    res = await client.receive_json()
    assert res["success"], res
    assert res["result"]["project_loaded"] is False


async def test_knx_subscribe_telegrams_command(
    hass: HomeAssistant, knx: KNXTestKit, hass_ws_client: WebSocketGenerator
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

    client = await hass_ws_client(hass)

    await client.send_json({"id": 6, "type": "knx/subscribe_telegrams"})

    res = await client.receive_json()
    assert res["success"], res

    # send incoming events
    await knx.receive_read("1/2/3")
    await knx.receive_write("1/3/4", True)
    await knx.receive_write("1/3/4", False)
    await knx.receive_individual_address_read()
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
    assert res["event"]["direction"] == "group_monitor_incoming"
    assert res["event"]["timestamp"] is not None

    res = await client.receive_json()
    assert res["event"]["destination_address"] == "1/3/4"
    assert res["event"]["payload"] == "0b000001"
    assert res["event"]["type"] == "GroupValueWrite"
    assert res["event"]["source_address"] == "1.2.3"
    assert res["event"]["direction"] == "group_monitor_incoming"
    assert res["event"]["timestamp"] is not None

    res = await client.receive_json()
    assert res["event"]["destination_address"] == "1/3/4"
    assert res["event"]["payload"] == "0b000000"
    assert res["event"]["type"] == "GroupValueWrite"
    assert res["event"]["source_address"] == "1.2.3"
    assert res["event"]["direction"] == "group_monitor_incoming"
    assert res["event"]["timestamp"] is not None

    res = await client.receive_json()
    assert res["event"]["destination_address"] == "1/3/8"
    assert res["event"]["payload"] == "0x3445"
    assert res["event"]["type"] == "GroupValueWrite"
    assert res["event"]["source_address"] == "1.2.3"
    assert res["event"]["direction"] == "group_monitor_incoming"
    assert res["event"]["timestamp"] is not None

    res = await client.receive_json()
    assert res["event"]["destination_address"] == "1/2/4"
    assert res["event"]["payload"] == "0b000001"
    assert res["event"]["type"] == "GroupValueWrite"
    assert (
        res["event"]["source_address"] == "0.0.0"
    )  # needs to be the IA currently connected to
    assert res["event"]["direction"] == "group_monitor_outgoing"
    assert res["event"]["timestamp"] is not None
