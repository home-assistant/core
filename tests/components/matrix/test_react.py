"""Test the react service."""

import pytest

from homeassistant.components.matrix import DOMAIN, MatrixBot
from homeassistant.components.matrix.const import (
    ATTR_MESSAGE_ID,
    ATTR_REACTION,
    ATTR_ROOM,
    SERVICE_REACT,
)
from homeassistant.core import Event, HomeAssistant

from .conftest import TEST_JOINABLE_ROOMS


async def test_send_message(
    hass: HomeAssistant,
    matrix_bot: MatrixBot,
    image_path,
    matrix_events: list[Event],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the send_message service."""

    await hass.async_start()
    assert len(matrix_events) == 0
    await matrix_bot._login()

    # Send a reaction.
    room = list(TEST_JOINABLE_ROOMS)[0]
    data = {ATTR_MESSAGE_ID: "message_id", ATTR_ROOM: room, ATTR_REACTION: "👍"}
    await hass.services.async_call(DOMAIN, SERVICE_REACT, data, blocking=True)

    assert f"Message delivered to room '{room}'" in caplog.messages
