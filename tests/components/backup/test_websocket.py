"""Tests for the Backup integration."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.backup.const import DATA_MANAGER
from homeassistant.components.backup.models import BaseBackup
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .common import TEST_BACKUP, BackupSyncAgentTest, setup_backup_integration

from tests.typing import WebSocketGenerator


@pytest.fixture
def sync_access_token_proxy(
    access_token_fixture_name: str,
    request: pytest.FixtureRequest,
) -> str:
    """Non-async proxy for the *_access_token fixture.

    Workaround for https://github.com/pytest-dev/pytest-asyncio/issues/112
    """
    return request.getfixturevalue(access_token_fixture_name)


@pytest.mark.parametrize(
    "with_hassio",
    [
        pytest.param(True, id="with_hassio"),
        pytest.param(False, id="without_hassio"),
    ],
)
async def test_info(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    with_hassio: bool,
) -> None:
    """Test getting backup info."""
    await setup_backup_integration(hass, with_hassio=with_hassio)

    hass.data[DATA_MANAGER].backups = {TEST_BACKUP.slug: TEST_BACKUP}

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.load_backups",
            AsyncMock(),
        ),
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backups",
            return_value={TEST_BACKUP.slug: TEST_BACKUP},
        ),
    ):
        await client.send_json_auto_id({"type": "backup/info"})
        assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    "backup_content",
    [
        pytest.param(TEST_BACKUP, id="with_backup_content"),
        pytest.param(None, id="without_backup_content"),
    ],
)
@pytest.mark.parametrize(
    "with_hassio",
    [
        pytest.param(True, id="with_hassio"),
        pytest.param(False, id="without_hassio"),
    ],
)
async def test_details(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    with_hassio: bool,
    backup_content: BaseBackup | None,
) -> None:
    """Test getting backup info."""
    await setup_backup_integration(hass, with_hassio=with_hassio)

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.backup.manager.BackupManager.async_get_backup",
        return_value=backup_content,
    ):
        await client.send_json_auto_id({"type": "backup/details", "slug": "abc123"})
        assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    "with_hassio",
    [
        pytest.param(True, id="with_hassio"),
        pytest.param(False, id="without_hassio"),
    ],
)
async def test_remove(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    with_hassio: bool,
) -> None:
    """Test removing a backup file."""
    await setup_backup_integration(hass, with_hassio=with_hassio)

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.backup.manager.BackupManager.async_remove_backup",
    ):
        await client.send_json_auto_id({"type": "backup/remove", "slug": "abc123"})
        assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    "with_hassio",
    [
        pytest.param(True, id="with_hassio"),
        pytest.param(False, id="without_hassio"),
    ],
)
async def test_generate(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    with_hassio: bool,
) -> None:
    """Test generating a backup."""
    await setup_backup_integration(hass, with_hassio=with_hassio)

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_create_backup",
            return_value=TEST_BACKUP,
        ),
    ):
        await client.send_json_auto_id({"type": "backup/generate"})
        assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    "access_token_fixture_name",
    ["hass_access_token", "hass_supervisor_access_token"],
)
@pytest.mark.parametrize(
    ("with_hassio"),
    [
        pytest.param(True, id="with_hassio"),
        pytest.param(False, id="without_hassio"),
    ],
)
async def test_backup_end(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    sync_access_token_proxy: str,
    *,
    access_token_fixture_name: str,
    with_hassio: bool,
) -> None:
    """Test handling of post backup actions from a WS command."""
    await setup_backup_integration(hass, with_hassio=with_hassio)

    client = await hass_ws_client(hass, sync_access_token_proxy)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.backup.manager.BackupManager.async_post_backup_actions",
    ):
        await client.send_json_auto_id({"type": "backup/end"})
        assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    "access_token_fixture_name",
    ["hass_access_token", "hass_supervisor_access_token"],
)
@pytest.mark.parametrize(
    ("with_hassio"),
    [
        pytest.param(True, id="with_hassio"),
        pytest.param(False, id="without_hassio"),
    ],
)
async def test_backup_start(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    sync_access_token_proxy: str,
    *,
    access_token_fixture_name: str,
    with_hassio: bool,
) -> None:
    """Test handling of pre backup actions from a WS command."""
    await setup_backup_integration(hass, with_hassio=with_hassio)

    client = await hass_ws_client(hass, sync_access_token_proxy)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.backup.manager.BackupManager.async_pre_backup_actions",
    ):
        await client.send_json_auto_id({"type": "backup/start"})
        assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    "exception",
    [
        TimeoutError(),
        HomeAssistantError("Boom"),
        Exception("Boom"),
    ],
)
async def test_backup_end_excepion(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    hass_supervisor_access_token: str,
    exception: Exception,
) -> None:
    """Test exception handling while running post backup actions from a WS command."""
    await setup_backup_integration(hass, with_hassio=True)

    client = await hass_ws_client(hass, hass_supervisor_access_token)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.backup.manager.BackupManager.async_post_backup_actions",
        side_effect=exception,
    ):
        await client.send_json_auto_id({"type": "backup/end"})
        assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    "exception",
    [
        TimeoutError(),
        HomeAssistantError("Boom"),
        Exception("Boom"),
    ],
)
async def test_backup_start_excepion(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    hass_supervisor_access_token: str,
    exception: Exception,
) -> None:
    """Test exception handling while running pre backup actions from a WS command."""
    await setup_backup_integration(hass, with_hassio=True)

    client = await hass_ws_client(hass, hass_supervisor_access_token)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.backup.manager.BackupManager.async_pre_backup_actions",
        side_effect=exception,
    ):
        await client.send_json_auto_id({"type": "backup/start"})
        assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    "with_hassio",
    [
        pytest.param(True, id="with_hassio"),
        pytest.param(False, id="without_hassio"),
    ],
)
async def test_agents_info(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    with_hassio: bool,
) -> None:
    """Test getting backup agents info."""
    await setup_backup_integration(hass, with_hassio=with_hassio)
    hass.data[DATA_MANAGER].sync_agents = {"domain.test": BackupSyncAgentTest("test")}

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "backup/agents/info"})
    assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    "with_hassio",
    [
        pytest.param(True, id="with_hassio"),
        pytest.param(False, id="without_hassio"),
    ],
)
async def test_agents_synced(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    with_hassio: bool,
) -> None:
    """Test getting backup agents synced details."""
    await setup_backup_integration(hass, with_hassio=with_hassio)
    hass.data[DATA_MANAGER].sync_agents = {"domain.test": BackupSyncAgentTest("test")}

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id({"type": "backup/agents/synced"})
    assert await client.receive_json() == snapshot


@pytest.mark.parametrize(
    "with_hassio",
    [
        pytest.param(True, id="with_hassio"),
        pytest.param(False, id="without_hassio"),
    ],
)
async def test_agents_download(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    with_hassio: bool,
) -> None:
    """Test WS command to start downloading a synced backup."""
    await setup_backup_integration(hass, with_hassio=with_hassio)
    hass.data[DATA_MANAGER].sync_agents = {"domain.test": BackupSyncAgentTest("test")}

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id(
        {
            "type": "backup/agents/download",
            "slug": "abc123",
            "agent": "domain.test",
            "sync_id": "abc123",
        }
    )
    with patch.object(BackupSyncAgentTest, "async_download_backup") as download_mock:
        assert await client.receive_json() == snapshot
        assert download_mock.call_args[1] == {
            "id": "abc123",
            "path": Path(hass.config.path("backup"), "abc123.tar"),
        }


async def test_agents_download_exception(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test WS command to start downloading a synced backup throwing an exception."""
    await setup_backup_integration(hass)
    hass.data[DATA_MANAGER].sync_agents = {"domain.test": BackupSyncAgentTest("test")}

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id(
        {
            "type": "backup/agents/download",
            "slug": "abc123",
            "agent": "domain.test",
            "sync_id": "abc123",
        }
    )
    with patch.object(BackupSyncAgentTest, "async_download_backup") as download_mock:
        download_mock.side_effect = Exception("Boom")
        assert await client.receive_json() == snapshot


async def test_agents_download_unknown_agent(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test downloading a synced backup with an unknown agent."""
    await setup_backup_integration(hass)

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json_auto_id(
        {
            "type": "backup/agents/download",
            "slug": "abc123",
            "agent": "domain.test",
            "sync_id": "abc123",
        }
    )
    assert await client.receive_json() == snapshot
