"""Test the builtin backup platform."""

from __future__ import annotations

from collections.abc import Generator
import json
from tarfile import TarError
from unittest.mock import MagicMock, patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.backup import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import TEST_BACKUP_ABC123, TEST_BACKUP_PATH_ABC123

from tests.typing import WebSocketGenerator


@pytest.fixture(name="read_backup")
def read_backup_fixture() -> Generator[MagicMock]:
    """Mock read backup."""
    with (
        patch("pathlib.Path.glob", return_value=[TEST_BACKUP_PATH_ABC123]),
        patch(
            "homeassistant.components.backup.backup.read_backup",
            return_value=TEST_BACKUP_ABC123,
        ) as read_backup,
    ):
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

    await client.send_json_auto_id({"type": "backup/agents/info"})
    assert await client.receive_json() == snapshot

    await client.send_json_auto_id({"type": "backup/info"})
    assert await client.receive_json() == snapshot
