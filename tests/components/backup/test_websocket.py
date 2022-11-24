"""Tests for the Backup integration."""
from collections.abc import Awaitable, Callable
from unittest.mock import patch

from aiohttp import ClientWebSocketResponse
import pytest

from spencerassistant.core import spencerAssistant

from .common import TEST_BACKUP, setup_backup_integration


async def test_info(
    hass: spencerAssistant,
    hass_ws_client: Callable[[spencerAssistant], Awaitable[ClientWebSocketResponse]],
) -> None:
    """Test getting backup info."""
    await setup_backup_integration(hass)

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    with patch(
        "spencerassistant.components.backup.websocket.BackupManager.get_backups",
        return_value={TEST_BACKUP.slug: TEST_BACKUP},
    ):

        await client.send_json({"id": 1, "type": "backup/info"})
        msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["success"]
    assert msg["result"] == {"backing_up": False, "backups": [TEST_BACKUP.as_dict()]}


async def test_remove(
    hass: spencerAssistant,
    hass_ws_client: Callable[[spencerAssistant], Awaitable[ClientWebSocketResponse]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removing a backup file."""
    await setup_backup_integration(hass)

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    with patch(
        "spencerassistant.components.backup.websocket.BackupManager.remove_backup",
    ):
        await client.send_json({"id": 1, "type": "backup/remove", "slug": "abc123"})
        msg = await client.receive_json()

        assert msg["id"] == 1
        assert msg["success"]


async def test_generate(
    hass: spencerAssistant,
    hass_ws_client: Callable[[spencerAssistant], Awaitable[ClientWebSocketResponse]],
) -> None:
    """Test removing a backup file."""
    await setup_backup_integration(hass)

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    with patch(
        "spencerassistant.components.backup.websocket.BackupManager.generate_backup",
        return_value=TEST_BACKUP,
    ):
        await client.send_json({"id": 1, "type": "backup/generate"})
        msg = await client.receive_json()

        assert msg["id"] == 1
        assert msg["success"]
        assert msg["result"] == TEST_BACKUP.as_dict()
