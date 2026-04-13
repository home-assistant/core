"""Test MatrixBot._join."""

import pytest

from homeassistant.components.matrix import MatrixBot
from homeassistant.components.matrix.const import DOMAIN
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import (
    FIXED_ENTRY_ID,
    MOCK_CONFIG_DATA,
    MOCK_NOTIFY_CONFIG,
    TEST_BAD_ROOM,
    TEST_JOINABLE_ROOMS,
    TEST_MXID,
)

from tests.common import MockConfigEntry


async def test_join(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_client,
    mock_store,
    mock_allowed_path,
) -> None:
    """Test joining configured rooms."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_DATA,
        unique_id=TEST_MXID,
        entry_id=FIXED_ENTRY_ID,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert await async_setup_component(hass, NOTIFY_DOMAIN, MOCK_NOTIFY_CONFIG)
    await hass.async_block_till_done()

    matrix_bot: MatrixBot = entry.runtime_data

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

    assert matrix_bot._listening_rooms == TEST_JOINABLE_ROOMS
