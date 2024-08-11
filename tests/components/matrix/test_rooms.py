"""Test MatrixBot._join."""

import pytest

from homeassistant.components.matrix import MatrixBot
from homeassistant.components.matrix.const import DOMAIN as MATRIX_DOMAIN
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import MOCK_CONFIG_DATA, TEST_BAD_ROOM, TEST_JOINABLE_ROOMS


async def test_join(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_client,
    mock_save_json,
    mock_allowed_path,
) -> None:
    """Test joining configured rooms."""
    assert await async_setup_component(hass, MATRIX_DOMAIN, MOCK_CONFIG_DATA)
    assert await async_setup_component(hass, NOTIFY_DOMAIN, MOCK_CONFIG_DATA)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Accessing hass.data in tests is not desirable, but all the tests here
    # currently do this.
    matrix_bot = hass.data[MATRIX_DOMAIN]

    for room_id in TEST_JOINABLE_ROOMS:
        assert f"Joined or already in room '{room_id}'" in caplog.messages

    # Joining a disallowed room should not raise an exception.
    matrix_bot._listening_rooms = {TEST_BAD_ROOM: TEST_BAD_ROOM}
    await matrix_bot._join_rooms()
    assert (
        f"Could not join room '{TEST_BAD_ROOM}': JoinError: Not allowed to join this room."
        in caplog.messages
    )


async def test_resolve_aliases(hass: HomeAssistant, matrix_bot: MatrixBot) -> None:
    """Test resolving configured room aliases into room ids."""

    await hass.async_start()
    assert matrix_bot._listening_rooms == TEST_JOINABLE_ROOMS
