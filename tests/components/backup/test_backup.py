"""Test the builtin backup platform."""

from __future__ import annotations

from collections.abc import Generator
from io import StringIO
import json
from pathlib import Path
from tarfile import TarError
from unittest.mock import MagicMock, mock_open, patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.backup import DOMAIN, AgentBackup
from homeassistant.core import HomeAssistant
from homeassistant.helpers.backup import async_initialize_backup
from homeassistant.setup import async_setup_component

from .common import (
    TEST_BACKUP_ABC123,
    TEST_BACKUP_DEF456,
    TEST_BACKUP_PATH_ABC123,
    TEST_BACKUP_PATH_DEF456,
)

from tests.typing import ClientSessionGenerator, WebSocketGenerator


def mock_read_backup(backup_path: Path) -> AgentBackup:
    """Mock read backup."""
    mock_backups = {
        "abc123": TEST_BACKUP_ABC123,
        "custom_def456": TEST_BACKUP_DEF456,
    }
    return mock_backups[backup_path.stem]


@pytest.fixture(name="read_backup")
def read_backup_fixture(path_glob: MagicMock) -> Generator[MagicMock]:
    """Mock read backup."""
    with patch(
        "homeassistant.components.backup.backup.read_backup",
        side_effect=mock_read_backup,
    ) as read_backup:
        yield read_backup


@pytest.mark.parametrize(
    "side_effect",
    [
        mock_read_backup,
        OSError("Boom"),
        TarError("Boom"),
        json.JSONDecodeError("Boom", "test", 1),
        KeyError("Boom"),
    ],
)
async def test_load_backups(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    read_backup: MagicMock,
    side_effect: Exception | None,
) -> None:
    """Test load backups."""
    async_initialize_backup(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)
    read_backup.side_effect = side_effect

    # list agents
    await client.send_json_auto_id({"type": "backup/agents/info"})
    assert await client.receive_json() == snapshot

    # load and list backups
    await client.send_json_auto_id({"type": "backup/info"})
    assert await client.receive_json() == snapshot


async def test_upload(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test upload backup."""
    async_initialize_backup(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    client = await hass_client()
    open_mock = mock_open()

    with (
        patch("pathlib.Path.open", open_mock),
        patch("shutil.move") as move_mock,
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=TEST_BACKUP_ABC123,
        ),
    ):
        resp = await client.post(
            "/api/backup/upload?agent_id=backup.local",
            data={"file": StringIO("test")},
        )

    assert resp.status == 201
    assert open_mock.call_count == 1
    assert move_mock.call_count == 1
    assert move_mock.mock_calls[0].args[1].name == "Test_1970-01-01_00.00_00000000.tar"


@pytest.mark.usefixtures("read_backup")
@pytest.mark.parametrize(
    ("found_backups", "backup_id", "unlink_calls", "unlink_path"),
    [
        (
            [TEST_BACKUP_PATH_ABC123, TEST_BACKUP_PATH_DEF456],
            TEST_BACKUP_ABC123.backup_id,
            1,
            TEST_BACKUP_PATH_ABC123,
        ),
        (
            [TEST_BACKUP_PATH_ABC123, TEST_BACKUP_PATH_DEF456],
            TEST_BACKUP_DEF456.backup_id,
            1,
            TEST_BACKUP_PATH_DEF456,
        ),
        (([], TEST_BACKUP_ABC123.backup_id, 0, None)),
    ],
)
async def test_delete_backup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    path_glob: MagicMock,
    found_backups: list[Path],
    backup_id: str,
    unlink_calls: int,
    unlink_path: Path | None,
) -> None:
    """Test delete backup."""
    async_initialize_backup(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)
    path_glob.return_value = found_backups

    with (
        patch("pathlib.Path.unlink", autospec=True) as unlink,
    ):
        await client.send_json_auto_id(
            {"type": "backup/delete", "backup_id": backup_id}
        )
        assert await client.receive_json() == snapshot

    assert unlink.call_count == unlink_calls
    for call in unlink.mock_calls:
        assert call.args[0] == unlink_path
