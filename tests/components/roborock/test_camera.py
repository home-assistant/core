"""Test the Roborock live camera."""

from base64 import b64decode, b64encode
import json
from typing import Any
from unittest.mock import patch

import pytest
from roborock.roborock_typing import RoborockCommand
from vacuum_map_parser_base.config.drawable import Drawable

from homeassistant.components.roborock.const import (
    CONF_CAMERA_PIN_HASH,
    CONF_SHOW_ROOMS,
    CONF_SHOW_WALLS,
)
from homeassistant.components.roborock.util import camera_pin_digest
from homeassistant.components.websocket_api import TYPE_RESULT
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from .conftest import FakeDevice

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator

CAMERA_ENTITY = "camera.roborock_s7_maxv_camera"
PIN_HASH = camera_pin_digest("1234")
ANSWER_SDP = "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\n"


def _encoded(value: dict[str, Any]) -> str:
    """Encode a signaling payload the way the vacuum does."""
    return b64encode(json.dumps(value).encode("utf-8")).decode("ascii")


def _params(call: Any) -> dict[str, Any]:
    """Return the params keyword of a command.send call."""
    params = call.kwargs["params"]
    assert isinstance(params, dict)
    return params


async def _fake_send(command: RoborockCommand, params: Any = None) -> Any:
    """Return the signaling responses a camera-capable vacuum sends."""
    if command is RoborockCommand.GET_TURN_SERVER:
        return [{"url": "turn:turn.example:3478", "user": "viewer", "pwd": "secret"}]
    if command is RoborockCommand.GET_DEVICE_SDP:
        return [{"dev_sdp": _encoded({"sdp": ANSWER_SDP, "type": "answer"})}]
    if command is RoborockCommand.GET_DEVICE_ICE:
        return [
            {
                "dev_ice": [
                    _encoded(
                        {
                            "candidate": "candidate:1 1 UDP 1 192.0.2.1 9 typ host",
                            "sdpMid": "0",
                            "sdpMLineIndex": 0,
                        }
                    )
                ]
            }
        ]
    return ["ok"]


@pytest.mark.parametrize("platforms", [[Platform.CAMERA]])
async def test_camera_created_for_video_vacuum(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a camera entity is created only for a vacuum that supports video."""
    assert fake_vacuum.v1_properties is not None
    fake_vacuum.v1_properties.device_features.is_video_monitor_supported = True
    fake_vacuum.v1_properties.command.send.side_effect = _fake_send

    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(CAMERA_ENTITY) is not None
    assert len(hass.states.async_entity_ids("camera")) == 1
    entry = entity_registry.async_get(CAMERA_ENTITY)
    assert entry is not None
    assert entry.unique_id.endswith("_camera")


@pytest.mark.parametrize("platforms", [[Platform.CAMERA]])
async def test_no_camera_without_video_support(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    setup_entry: MockConfigEntry,
) -> None:
    """Test vacuums without live video do not get a camera entity."""
    assert hass.states.async_entity_ids("camera") == []


@pytest.mark.parametrize("platforms", [[Platform.CAMERA]])
async def test_webrtc_offer_and_candidate(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test an offer is signaled to the vacuum and the answer is returned."""
    assert fake_vacuum.v1_properties is not None
    fake_vacuum.v1_properties.device_features.is_video_monitor_supported = True
    fake_vacuum.v1_properties.command.send.side_effect = _fake_send
    hass.config_entries.async_update_entry(
        mock_roborock_entry, options={CONF_CAMERA_PIN_HASH: PIN_HASH}
    )

    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/offer",
            "entity_id": CAMERA_ENTITY,
            "offer": "v=0\r\n",
        }
    )
    result = await client.receive_json()
    assert result["type"] == TYPE_RESULT
    assert result["success"]
    subscription_id = result["id"]

    session = await client.receive_json()
    assert session["event"]["type"] == "session"
    session_id = session["event"]["session_id"]

    answer = await client.receive_json()
    assert answer["id"] == subscription_id
    assert answer["event"] == {"type": "answer", "answer": ANSWER_SDP}

    ice = await client.receive_json()
    assert ice["event"]["type"] == "candidate"
    assert "192.0.2.1" in ice["event"]["candidate"]["candidate"]

    send = fake_vacuum.v1_properties.command.send
    commands = [call.args[0] for call in send.await_args_list]
    assert RoborockCommand.CHECK_HOMESEC_PASSWORD in commands
    assert RoborockCommand.START_CAMERA_PREVIEW in commands
    start_call = next(
        call
        for call in send.await_args_list
        if call.args[0] is RoborockCommand.START_CAMERA_PREVIEW
    )
    assert _params(start_call)["password"] == PIN_HASH
    assert "1234" not in json.dumps(_params(start_call))

    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/candidate",
            "entity_id": CAMERA_ENTITY,
            "session_id": session_id,
            "candidate": {
                "candidate": "candidate:2 1 UDP 1 192.0.2.2 9 typ host",
                "sdpMLineIndex": 0,
            },
        }
    )
    candidate_result = await client.receive_json()
    assert candidate_result["success"]

    ice_call = next(
        call
        for call in send.await_args_list
        if call.args[0] is RoborockCommand.SEND_ICE_TO_ROBOT
    )
    forwarded = json.loads(b64decode(_params(ice_call)["app_ice"]))
    assert forwarded["candidate"].startswith("candidate:2")

    await client.close()
    await hass.async_block_till_done()
    stop_commands = [call.args[0] for call in send.await_args_list]
    assert RoborockCommand.STOP_CAMERA_PREVIEW in stop_commands


@pytest.mark.parametrize("platforms", [[Platform.CAMERA]])
async def test_offer_requires_video_pin(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test live view is refused until a video PIN is saved."""
    assert fake_vacuum.v1_properties is not None
    fake_vacuum.v1_properties.device_features.is_video_monitor_supported = True
    fake_vacuum.v1_properties.command.send.side_effect = _fake_send

    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "camera/webrtc/offer",
            "entity_id": CAMERA_ENTITY,
            "offer": "v=0\r\n",
        }
    )
    result = await client.receive_json()
    assert result["success"]
    await client.receive_json()
    error = await client.receive_json()
    assert error["event"]["type"] == "error"
    assert error["event"]["code"] == "webrtc_offer_failed"
    assert "PIN" in error["event"]["message"]

    commands = [
        call.args[0] for call in fake_vacuum.v1_properties.command.send.await_args_list
    ]
    assert RoborockCommand.START_CAMERA_PREVIEW not in commands


async def test_options_flow_stores_pin_digest(
    hass: HomeAssistant, mock_roborock_entry: MockConfigEntry
) -> None:
    """Test the options flow stores the video PIN digest, not the PIN."""
    with patch("homeassistant.components.roborock.roborock_storage"):
        await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(
            mock_roborock_entry.entry_id
        )
        assert result["step_id"] == "drawables"
        with patch(
            "homeassistant.components.roborock.async_setup_entry", return_value=True
        ):
            result = await hass.config_entries.options.async_configure(
                result["flow_id"],
                user_input={
                    Drawable.PREDICTED_PATH: True,
                    CONF_SHOW_ROOMS: True,
                    CONF_SHOW_WALLS: True,
                    "camera_pin": "1234",
                },
            )
            await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_roborock_entry.options[CONF_CAMERA_PIN_HASH] == PIN_HASH
    assert "1234" not in mock_roborock_entry.options[CONF_CAMERA_PIN_HASH]
