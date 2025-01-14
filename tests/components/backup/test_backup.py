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

from homeassistant.components.backup import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import TEST_BACKUP_ABC123, TEST_BACKUP_PATH_ABC123

from tests.typing import ClientSessionGenerator, WebSocketGenerator


@pytest.fixture(name="read_backup")
def read_backup_fixture(path_glob: MagicMock) -> Generator[MagicMock]:
    """Mock read backup."""
    with patch(
        "homeassistant.components.backup.backup.read_backup",
        return_value=TEST_BACKUP_ABC123,
    ) as read_backup:
        yield read_backup


@pytest.mark.parametrize(
    "side_effect",
    [
        None,
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
    assert move_mock.mock_calls[0].args[1].name == "abc123.tar"


@pytest.mark.usefixtures("read_backup")
@pytest.mark.parametrize(
    ("found_backups", "backup_exists", "unlink_calls"),
    [
        ([TEST_BACKUP_PATH_ABC123], True, 1),
        ([TEST_BACKUP_PATH_ABC123], False, 0),
        (([], True, 0)),
    ],
)
async def test_delete_backup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    path_glob: MagicMock,
    found_backups: list[Path],
    backup_exists: bool,
    unlink_calls: int,
) -> None:
    """Test delete backup."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)
    path_glob.return_value = found_backups

    with (
        patch("pathlib.Path.exists", return_value=backup_exists),
        patch("pathlib.Path.unlink") as unlink,
    ):
        await client.send_json_auto_id(
            {"type": "backup/delete", "backup_id": TEST_BACKUP_ABC123.backup_id}
        )
        assert await client.receive_json() == snapshot

    assert unlink.call_count == unlink_calls
