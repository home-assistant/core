"""Test the send_message service."""

from homeassistant.components.matrix import (
    ATTR_FORMAT,
    ATTR_IMAGES,
    DOMAIN as MATRIX_DOMAIN,
    MatrixBot,
)
from homeassistant.components.matrix.const import (
    FORMAT_TEXT,
    FORMAT_HTML,
    FORMAT_NOTICE,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.components.notify import ATTR_DATA, ATTR_MESSAGE, ATTR_TARGET
from homeassistant.core import HomeAssistant

from tests.components.matrix.conftest import TEST_BAD_ROOM, TEST_JOINABLE_ROOMS
import pytest


@pytest.mark.parametrize(
    "test_name, test_params",
    [
        (
            "Text message",
            {
                "data": {
                    ATTR_MESSAGE: "Test text message",
                    ATTR_DATA: {ATTR_FORMAT: FORMAT_TEXT},
                    ATTR_TARGET: list(TEST_JOINABLE_ROOMS.keys()),
                },
                "expected_result": {
                    "target_rooms": list(TEST_JOINABLE_ROOMS.keys()),
                    "message_type": "m.room.message",
                    "content": {"msgtype": "m.text", "body": "Test text message"},
                },
            },
        ),
        (
            "HTML message",
            {
                "data": {
                    ATTR_MESSAGE: "Test <b>html</b> message",
                    ATTR_DATA: {ATTR_FORMAT: FORMAT_HTML},
                    ATTR_TARGET: list(TEST_JOINABLE_ROOMS.keys()),
                },
                "expected_result": {
                    "target_rooms": list(TEST_JOINABLE_ROOMS.keys()),
                    "message_type": "m.room.message",
                    "content": {
                        "msgtype": "m.text",
                        "body": "Test <b>html</b> message",
                        "format": "org.matrix.custom.html",
                        "formatted_body": "Test <b>html</b> message",
                    },
                },
            },
        ),
        (
            "Bot (notice) message",
            {
                "data": {
                    ATTR_MESSAGE: "Test bot (notice) message",
                    ATTR_DATA: {ATTR_FORMAT: FORMAT_NOTICE},
                    ATTR_TARGET: list(TEST_JOINABLE_ROOMS.keys()),
                },
                "expected_result": {
                    "target_rooms": list(TEST_JOINABLE_ROOMS.keys()),
                    "message_type": "m.room.message",
                    "content": {
                        "msgtype": "m.notice",
                        "body": "Test bot (notice) message",
                    },
                },
            },
        ),
    ],
)
async def test_send_message(
    hass: HomeAssistant,
    matrix_bot: MatrixBot,
    image_path,
    matrix_events,
    caplog,
    test_name,
    test_params,
):
    """Test the send_message service."""

    await hass.async_start()
    assert len(matrix_events) == 0
    await matrix_bot._login()

    await hass.services.async_call(
        MATRIX_DOMAIN, SERVICE_SEND_MESSAGE, test_params["data"], blocking=True
    )

    matrix_bot._handle_multi_room_send.assert_called_once_with(
        **test_params["expected_result"]
    )

    for room_alias_or_id in TEST_JOINABLE_ROOMS:
        assert f"Message delivered to room '{room_alias_or_id}'" in caplog.messages


async def test_send_image(
    hass: HomeAssistant, matrix_bot: MatrixBot, image_path, matrix_events, caplog
):
    """Test send a message with an attached image"""

    await hass.async_start()
    assert len(matrix_events) == 0
    await matrix_bot._login()

    data = {
        ATTR_MESSAGE: "Test <b>html</b> message",
        ATTR_TARGET: list(TEST_JOINABLE_ROOMS),
        ATTR_DATA: {ATTR_IMAGES: [image_path.name]},
    }
    await hass.services.async_call(
        MATRIX_DOMAIN, SERVICE_SEND_MESSAGE, data, blocking=True
    )

    for room_alias_or_id in TEST_JOINABLE_ROOMS:
        assert f"Message delivered to room '{room_alias_or_id}'" in caplog.messages


async def test_unsendable_message(
    hass: HomeAssistant, matrix_bot: MatrixBot, matrix_events, caplog
):
    """Test the send_message service with an invalid room."""
    assert len(matrix_events) == 0
    await matrix_bot._login()

    data = {ATTR_MESSAGE: "Test message", ATTR_TARGET: TEST_BAD_ROOM}

    await hass.services.async_call(
        MATRIX_DOMAIN, SERVICE_SEND_MESSAGE, data, blocking=True
    )

    assert (
        f"Unable to deliver message to room '{TEST_BAD_ROOM}': ErrorResponse: Cannot send a message in this room."
        in caplog.messages
    )
