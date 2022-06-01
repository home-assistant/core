"""Test MatrixBot._join."""

from homeassistant.components.matrix import MatrixBot

from tests.components.matrix.conftest import TEST_BAD_ROOM, TEST_JOINABLE_ROOMS


async def test_join(matrix_bot: MatrixBot, caplog):
    """Test joining configured rooms."""

    # Join configured rooms.
    await matrix_bot._join_rooms()
    for room_id in TEST_JOINABLE_ROOMS:
        assert f"Joined or already in room '{room_id}'" in caplog.messages

    # Joining a disallowed room should not raise an exception.
    matrix_bot._listening_rooms = [TEST_BAD_ROOM]
    await matrix_bot._join_rooms()
    assert (
        f"Could not join room '{TEST_BAD_ROOM}': JoinError: Not allowed to join this room."
        in caplog.messages
    )
