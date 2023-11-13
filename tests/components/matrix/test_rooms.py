"""Test MatrixBot._join."""

from homeassistant.components.matrix import MatrixBot

from tests.components.matrix.conftest import TEST_BAD_ROOM, TEST_JOINABLE_ROOMS


async def test_join(hass, matrix_bot: MatrixBot, caplog):
    """Test joining configured rooms."""

    await hass.async_start()
    for room_id in TEST_JOINABLE_ROOMS:
        assert f"Joined or already in room '{room_id}'" in caplog.messages

    # Joining a disallowed room should not raise an exception.
    matrix_bot._listening_rooms = {TEST_BAD_ROOM: TEST_BAD_ROOM}
    await matrix_bot._join_rooms()
    assert (
        f"Could not join room '{TEST_BAD_ROOM}': JoinError: Not allowed to join this room."
        in caplog.messages
    )


async def test_resolve_aliases(hass, matrix_bot: MatrixBot):
    """Test resolving configured room aliases into room ids."""

    await hass.async_start()
    assert matrix_bot._listening_rooms == TEST_JOINABLE_ROOMS
